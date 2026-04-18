import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import traceback

# 設定エリア
FEE_RATE = -0.0001       # Maker手数料
LOT_SIZE = 0.001         # BTC
GRID_INTERVAL = 30000    # 刻み
PROFIT_MARGIN = 40000    # 利確幅

# テクニカル指標設定
RSI_PERIOD = 14         
RSI_OVERBOUGHT = 70     
RSI_OVERSOLD = 30       
SUPPORT_WINDOW = 50     

class FXTradingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GMO Real-Time Asset Manager")
        self.root.geometry("750x1050") 

        self.is_running = False
        self.initial_balance = 100000
        self.cash = self.initial_balance  
        self.positions = []               # 保有ポジションリスト
        self.equity_history = []          # 総資産の推移
        
        self.df_technical = pd.DataFrame() 

        # UI
        top_frame = tk.Frame(root)
        top_frame.pack(pady=10)
        
        self.label_title = tk.Label(top_frame, text="GMO Real-Time Asset Manager", font=("Helvetica", 16, "bold"))
        self.label_title.pack()

        # 価格表示
        price_frame = tk.Frame(top_frame, relief="ridge", borderwidth=2)
        price_frame.pack(pady=10, padx=10, fill="x")

        # Bid
        self.frame_bid = tk.Frame(price_frame)
        self.frame_bid.pack(side="left", expand=True)
        tk.Label(self.frame_bid, text="売却価格 (Bid)", font=("Helvetica", 10), fg="blue").pack()
        self.label_bid = tk.Label(self.frame_bid, text="---", font=("Helvetica", 18, "bold"), fg="blue")
        self.label_bid.pack()

        # LTP
        self.frame_ltp = tk.Frame(price_frame)
        self.frame_ltp.pack(side="left", expand=True)
        tk.Label(self.frame_ltp, text="現在値 (LTP)", font=("Helvetica", 8), fg="gray").pack()
        self.label_ltp = tk.Label(self.frame_ltp, text="---", font=("Helvetica", 12), fg="black")
        self.label_ltp.pack()

        # Ask
        self.frame_ask = tk.Frame(price_frame)
        self.frame_ask.pack(side="left", expand=True)
        tk.Label(self.frame_ask, text="購入価格 (Ask)", font=("Helvetica", 10), fg="red").pack()
        self.label_ask = tk.Label(self.frame_ask, text="---", font=("Helvetica", 18, "bold"), fg="red")
        self.label_ask.pack()

        # 資産表示
        asset_frame = tk.LabelFrame(root, text="Asset Management", font=("Helvetica", 12, "bold"), padx=10, pady=10)
        asset_frame.pack(pady=5, padx=10, fill="x")

        # 現金残高
        self.label_cash = tk.Label(asset_frame, text=f"現金残高: {self.cash:,} 円", font=("Helvetica", 14), fg="black")
        self.label_cash.pack(anchor="w")
        
        # 総資産（時価評価額）
        self.label_total_equity = tk.Label(asset_frame, text=f"総資産(時価): {self.cash:,} 円", font=("Helvetica", 16, "bold"), fg="green")
        self.label_total_equity.pack(anchor="w")

        # ポジション情報
        self.label_pos_info = tk.Label(asset_frame, text="保有ポジション: 0 BTC (評価額: 0円)", font=("Helvetica", 10), fg="gray")
        self.label_pos_info.pack(anchor="w")


        # 指標表示エリア
        indicator_frame = tk.LabelFrame(root, text="Technical Indicators", font=("Helvetica", 10), padx=10, pady=5)
        indicator_frame.pack(pady=5, padx=10, fill="x")

        self.label_rsi = tk.Label(indicator_frame, text="RSI(14): ---", font=("Helvetica", 12))
        self.label_rsi.grid(row=0, column=0, padx=15)
        
        self.label_zscore = tk.Label(indicator_frame, text="Z-Score: ---", font=("Helvetica", 12))
        self.label_zscore.grid(row=0, column=1, padx=15)

        self.label_support = tk.Label(indicator_frame, text="Support: ---", font=("Helvetica", 12))
        self.label_support.grid(row=0, column=2, padx=15)

        self.label_judgment = tk.Label(root, text="【AI判断】 待機中", font=("Helvetica", 14, "bold"), fg="gray", bg="#f0f0f0", pady=10)
        self.label_judgment.pack(fill="x")

        # ボタン
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)
        self.btn_start = tk.Button(btn_frame, text="分析＆稼働開始", bg="blue", fg="white", font=("Helvetica", 12), width=15, command=self.start_trading)
        self.btn_start.pack(side=tk.LEFT, padx=10)
        self.btn_stop = tk.Button(btn_frame, text="停止", bg="red", fg="white", font=("Helvetica", 12), width=10, command=self.stop_trading)
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        self.btn_stop["state"] = "disabled"

        # グラフ
        self.fig, self.ax = plt.subplots(figsize=(6, 3), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(pady=5)

        # ログ
        self.log_area = scrolledtext.ScrolledText(root, width=80, height=8, state='disabled')
        self.log_area.pack(pady=10, padx=10)
        
        self.log("システム起動。現金管理モード実装済み。")

    def log(self, message):
        try:
            self.log_area.config(state='normal')
            current_time = time.strftime("%H:%M:%S")
            self.log_area.insert(tk.END, f"[{current_time}] {message}\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
        except:
            pass

    def start_trading(self):
        if not self.is_running:
            self.is_running = True
            self.label_title.config(text="● 稼働中", fg="green")
            self.btn_start["state"] = "disabled"
            self.btn_stop["state"] = "normal"
            self.cash = self.initial_balance # スタート時にリセット
            self.positions = []
            self.equity_history = [self.initial_balance]
            
            self.thread = threading.Thread(target=self.run_safely)
            self.thread.daemon = True 
            self.thread.start()

    def stop_trading(self):
        if self.is_running:
            self.is_running = False
            self.label_title.config(text="■ 停止中", fg="red")
            self.label_judgment.config(text="【AI判断】 停止", bg="gray", fg="white")
            self.btn_start["state"] = "normal"
            self.btn_stop["state"] = "disabled"
            self.log("停止しました。")

    def run_safely(self):
        try:
            self.trading_loop()
        except Exception as e:
            self.log(f"【エラー回避】処理を継続します: {e}")
            print(traceback.format_exc())
            time.sleep(5)
            if self.is_running:
                self.run_safely()

    def get_market_data(self):
        url = "https://api.coin.z.com/public/v1/ticker?symbol=BTC"
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            if data['status'] == 0:
                ticker = data['data'][0]
                return {
                    "ask": float(ticker['ask']),
                    "bid": float(ticker['bid']),
                    "ltp": float(ticker['last'])
                }
            return None
        except:
            return None


    
    def fetch_initial_data(self):
        self.log("過去データを構築中...")
        try:
            df = yf.download("BTC-JPY", period="1y", interval="1h", progress=False)
            if len(df) > 0:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
            return pd.DataFrame()
        except:
            return pd.DataFrame()
        

    def calculate_indicators(self, price):
        new_row = pd.DataFrame({"Close": [price]})
        self.df_technical = pd.concat([self.df_technical, new_row], ignore_index=True)
        
        if len(self.df_technical) > 500:
            self.df_technical = self.df_technical.iloc[-500:]

        df = self.df_technical.copy()

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        if loss.iloc[-1] == 0:
            current_rsi = 50
        else:
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            current_rsi = df['RSI'].iloc[-1]

        # Support
        df['Support'] = df['Close'].rolling(window=SUPPORT_WINDOW).min()
        current_support = df['Support'].iloc[-1]

        # Z-Score Proxy
        ma_200 = df['Close'].rolling(window=200).mean().iloc[-1]
        if pd.isna(ma_200): ma_200 = price 
        if pd.isna(current_rsi): current_rsi = 50 
        if pd.isna(current_support): current_support = price 

        deviation = ((price - ma_200) / ma_200) * 100
        
        return current_rsi, current_support, deviation

    def update_graph(self):
        if not self.is_running: return
        try:
            self.ax.clear()
            self.ax.plot(self.equity_history, color='blue', label='Total Equity')
            self.ax.set_title("Total Equity (Cash + Positions)")
            self.ax.grid(True)
            self.canvas.draw()
        except:
            pass

    def trading_loop(self):
        initial_df = self.fetch_initial_data()
        if not initial_df.empty:
            self.df_technical = initial_df[['Close']].copy()
            self.log(f"過去データロード完了。")
        else:
            self.df_technical = pd.DataFrame({"Close": [15000000] * 200})
            self.log("仮データで開始します。")

        market_data = self.get_market_data()
        if market_data:
            last_grid_price = market_data['bid']
        else:
            last_grid_price = 15000000

        while self.is_running:
            market = self.get_market_data()
            if market is None:
                time.sleep(2)
                continue

            current_bid = market['bid']
            current_ask = market['ask']
            current_ltp = market['ltp']

            # 指標計算
            rsi, support, z_score_proxy = self.calculate_indicators(current_ltp)

            # UI更新
            self.root.after(0, self.label_bid.config, {"text": f"{int(current_bid):,}"})
            self.root.after(0, self.label_ask.config, {"text": f"{int(current_ask):,}"})
            self.root.after(0, self.label_ltp.config, {"text": f"{int(current_ltp):,}"})

            # RSI & Z-Score
            rsi_text = f"RSI: {rsi:.1f}"
            rsi_color = "red" if rsi > RSI_OVERBOUGHT else "blue" if rsi < RSI_OVERSOLD else "black"
            self.root.after(0, self.label_rsi.config, {"text": rsi_text, "fg": rsi_color})
            
            z_text = f"乖離: {z_score_proxy:+.2f}%"
            z_color = "red" if z_score_proxy > 20 else "blue" if z_score_proxy < -20 else "black"
            self.root.after(0, self.label_zscore.config, {"text": z_text, "fg": z_color})

            try:
                if pd.isna(support) or np.isinf(support):
                    s_text = "Support: ---"
                else:
                    dist_to_support = current_ltp - support
                    s_text = f"Support: {int(support):,} (あと{int(dist_to_support)})"
                self.root.after(0, self.label_support.config, {"text": s_text})
            except:
                pass

            # 利確ロジック
            for i in range(len(self.positions) - 1, -1, -1):
                pos = self.positions[i]
                if current_bid >= pos["price"] + PROFIT_MARGIN:
                    
                    # 売却額（Bid × 数量）
                    revenue = current_bid * LOT_SIZE
                    # 手数料報酬
                    sell_fee_reward = revenue * abs(FEE_RATE)
                    
                    # 現金に戻す
                    total_revenue = revenue + sell_fee_reward
                    self.cash += total_revenue
                    
                    # 利益計算
                    buy_cost = (pos["price"] * LOT_SIZE) - (pos["price"] * LOT_SIZE * abs(FEE_RATE))
                    net_profit = total_revenue - buy_cost
                    
                    self.positions.pop(i)
                    self.root.after(0, self.log, f"【利確】RSI:{rsi:.1f} (益:+{net_profit:.2f}円) 現金回復")

            # 新規注文ロジック
            can_buy = False
            reason = ""
            bg_color = "#f0f0f0"
            fg_color = "gray"

            # 資金チェック
            required_cash = current_ask * LOT_SIZE
            if self.cash < required_cash:
                reason = "資金不足"
                bg_color = "#ffdddd"
                fg_color = "red"
            elif current_ask <= last_grid_price - GRID_INTERVAL:
                # テクニカル判定
                if rsi < RSI_OVERBOUGHT:
                    if z_score_proxy < 30: 
                        can_buy = True
                        reason = "適正"
                        if rsi < RSI_OVERSOLD:
                            reason = "売られすぎ"
                            bg_color = "#ffcccc"
                            fg_color = "red"
                        elif not pd.isna(support) and abs(current_ltp - support) < 20000:
                            reason = "サポート反発"
                            bg_color = "#ccffcc"
                            fg_color = "green"
                    else:
                        reason = "過熱警戒"
                        bg_color = "#ffffcc"
                        fg_color = "orange"
                else:
                    reason = "RSI高すぎ"
                    bg_color = "#ffffcc"
                    fg_color = "orange"

                if can_buy:
                    # 購入額
                    cost = current_ask * LOT_SIZE
                    # 手数料報酬
                    buy_fee_reward = cost * abs(FEE_RATE)
                    
                    # 現金を引く
                    actual_payment = cost - buy_fee_reward
                    self.cash -= actual_payment
                    
                    self.positions.append({"price": current_ask, "amount": LOT_SIZE})
                    self.root.after(0, self.log, f"★【AI購入】{int(current_ask)}円 (支払:{int(actual_payment)}円)")
                    last_grid_price = current_ask
                else
                    last_grid_price = current_ask

            elif current_ask > last_grid_price + GRID_INTERVAL:
                last_grid_price = current_ask

            # 判断パネル
            status_text = f"【AI判断】 GO! ({reason})" if can_buy else f"【AI判断】 {reason}" if reason else "【AI判断】 監視中..."
            self.root.after(0, self.label_judgment.config, {"text": status_text, "bg": bg_color, "fg": fg_color})


            positions_value = sum([current_bid * LOT_SIZE for _ in self.positions])
            
            # 総資産（Equity） = 現金 + ポジション評価額
            total_equity = self.cash + positions_value
            
            self.equity_history.append(total_equity)
            if len(self.equity_history) > 300: self.equity_history.pop(0)

            # 画面更新
            self.root.after(0, self.label_cash.config, {"text": f"現金残高: {int(self.cash):,} 円"})
            
            # 総資産の色
            equity_color = "green" if total_equity >= self.initial_balance else "red"
            self.root.after(0, self.label_total_equity.config, {"text": f"総資産(時価): {int(total_equity):,} 円", "fg": equity_color})
            
            self.root.after(0, self.label_pos_info.config, {"text": f"保有ポジション: {len(self.positions)} (時価:{int(positions_value):,}円)"})
            
            self.root.after(0, self.update_graph)

            time.sleep(2)

if __name__ == "__main__":
    root = tk.Tk()
    app = FXTradingApp(root)
    root.mainloop()