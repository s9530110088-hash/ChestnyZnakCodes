import base64, csv, json, queue, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import requests

APP_TITLE="Честный ЗНАК — СУЗ API 3.0"
GROUP="meat"

class ContextMenu:
    def __init__(self,w):
        m=tk.Menu(w,tearoff=0)
        m.add_command(label="Вырезать",command=lambda:w.event_generate("<<Cut>>"))
        m.add_command(label="Копировать",command=lambda:w.event_generate("<<Copy>>"))
        m.add_command(label="Вставить",command=lambda:w.event_generate("<<Paste>>"))
        m.add_separator(); m.add_command(label="Выделить всё",command=lambda:w.event_generate("<<SelectAll>>"))
        w.bind("<Button-3>",lambda e:m.tk_popup(e.x_root,e.y_root))
        w.bind("<Control-a>",lambda e:(w.event_generate("<<SelectAll>>"),"break")[1])

class CryptoProSigner:
    def __init__(self, serial):
        self.serial=serial.strip().replace(" ","")
    def sign(self,text):
        import win32com.client, pythoncom
        pythoncom.CoInitialize()
        try:
            store=win32com.client.Dispatch("CAdESCOM.Store")
            store.Open(2,"My",2)
            cert=None
            for c in store.Certificates:
                if c.SerialNumber.upper()==self.serial.upper():
                    cert=c; break
            store.Close()
            if cert is None: raise RuntimeError("Сертификат с указанным серийным номером не найден в CurrentUser\\My")
            signer=win32com.client.Dispatch("CAdESCOM.CPSigner")
            signer.Certificate=cert
            data=win32com.client.Dispatch("CAdESCOM.CadesSignedData")
            data.ContentEncoding=1
            raw=text.encode("utf-8")
            data.Content=base64.b64encode(raw).decode("ascii")
            sig=data.SignCades(signer,1,True,0)
            return sig.replace("\r","").replace("\n","")
        finally:
            pythoncom.CoUninitialize()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE); self.geometry("1120x730"); self.minsize(980,650); self.configure(bg="#101318")
        self.http=requests.Session(); self.logq=queue.Queue(); self.last_order=None
        self.style(); self.ui(); self.after(150,self.drain)
    def style(self):
        s=ttk.Style(self); s.theme_use("clam")
        s.configure("TNotebook",background="#101318",borderwidth=0)
        s.configure("TNotebook.Tab",background="#1b2028",foreground="#cbd5e1",padding=(18,9))
        s.map("TNotebook.Tab",background=[("selected","#2563eb")],foreground=[("selected","white")])
        s.configure("TEntry",fieldbackground="#171b22",foreground="white",insertcolor="white")
        s.configure("TCombobox",fieldbackground="#171b22",foreground="white")
        s.configure("Treeview",background="#171b22",foreground="#e5e7eb",fieldbackground="#171b22",rowheight=28)
        s.configure("Treeview.Heading",background="#242a33",foreground="white")
    def ui(self):
        side=tk.Frame(self,bg="#151922",width=220); side.pack(side="left",fill="y")
        tk.Label(side,text="ЧЕСТНЫЙ ЗНАК",bg="#151922",fg="white",font=("Segoe UI",17,"bold")).pack(pady=(30,2))
        tk.Label(side,text="СУЗ API 3.0",bg="#151922",fg="#60a5fa").pack(pady=(0,25))
        for n,i in [("Заказ кодов",0),("Полученные КМ",1),("Подключение",2),("Настройки",3),("Журнал",4)]:
            tk.Button(side,text=n,command=lambda i=i:self.nb.select(i),anchor="w",bd=0,bg="#151922",fg="#d1d5db",activebackground="#2563eb",activeforeground="white",font=("Segoe UI",11),padx=25,pady=11).pack(fill="x")
        self.state=tk.Label(side,text="● Не подключено",bg="#151922",fg="#f59e0b"); self.state.pack(side="bottom",pady=25)
        main=tk.Frame(self,bg="#101318"); main.pack(side="left",fill="both",expand=True,padx=22,pady=20)
        self.nb=ttk.Notebook(main); self.nb.pack(fill="both",expand=True)
        self.order_tab(); self.codes_tab(); self.conn_tab(); self.settings_tab(); self.log_tab()
    def entry(self,p,label,default=""):
        f=tk.Frame(p,bg=p.cget("bg")); f.pack(fill="x",pady=6)
        tk.Label(f,text=label,bg=p.cget("bg"),fg="#aab2bf").pack(anchor="w")
        e=ttk.Entry(f); e.insert(0,default); e.pack(fill="x",pady=3); ContextMenu(e); return e
    def order_tab(self):
        t=tk.Frame(self.nb,bg="#101318"); self.nb.add(t,text="Заказ кодов")
        tk.Label(t,text="Новый заказ",bg="#101318",fg="white",font=("Segoe UI",20,"bold")).pack(anchor="w",pady=(20,18))
        b=tk.Frame(t,bg="#171b22"); b.pack(fill="x",padx=10)
        self.qty=self.entry(b,"Количество КМ","100"); self.gtin=self.entry(b,"GTIN","")
        self.template=self.entry(b,"Шаблон КМ","")
        self.payment=tk.StringVar(value="Оплата по нанесению")
        f=tk.Frame(b,bg="#171b22"); f.pack(fill="x",pady=6)
        tk.Label(f,text="Тип оплаты",bg="#171b22",fg="#aab2bf").pack(anchor="w")
        ttk.Combobox(f,textvariable=self.payment,state="readonly",values=["Оплата по нанесению","Оплата по эмиссии"]).pack(fill="x")
        tk.Button(t,text="ОФОРМИТЬ ЗАКАЗ",command=self.create_order,bg="#2563eb",fg="white",bd=0,font=("Segoe UI",11,"bold"),padx=20,pady=12).pack(anchor="e",pady=20)
        self.result=tk.Label(t,text="",bg="#101318",fg="#94a3b8",justify="left"); self.result.pack(anchor="w")
    def codes_tab(self):
        t=tk.Frame(self.nb,bg="#101318"); self.nb.add(t,text="Полученные КМ")
        top=tk.Frame(t,bg="#101318"); top.pack(fill="x",pady=10)
        tk.Button(top,text="Получить КМ по последнему заказу",command=self.get_codes,bg="#2563eb",fg="white",bd=0,padx=12,pady=8).pack(side="left")
        tk.Button(top,text="Экспорт CSV",command=self.export,bg="#334155",fg="white",bd=0,padx=12,pady=8).pack(side="right")
        self.codes=ttk.Treeview(t,columns=("code","gtin"),show="headings"); self.codes.heading("code",text="Код маркировки"); self.codes.heading("gtin",text="GTIN"); self.codes.column("code",width=760); self.codes.pack(fill="both",expand=True)
    def conn_tab(self):
        t=tk.Frame(self.nb,bg="#101318"); self.nb.add(t,text="Подключение")
        self.server=self.entry(t,"Адрес СУЗ","")
        self.oms=self.entry(t,"OMS ID","")
        self.token=self.entry(t,"Client Token","")
        self.cert=self.entry(t,"Серийный номер сертификата CryptoPro","")
        self.connection=self.entry(t,"omsConnection (если используется)","")
        tk.Button(t,text="ПРОВЕРИТЬ СУЗ",command=self.ping,bg="#2563eb",fg="white",bd=0,padx=18,pady=10).pack(anchor="e",pady=18)
        tk.Label(t,text="ИНН не запрашивается. Для реальной подписи нужен установленный CryptoPro CSP/CAdESCOM и сертификат в CurrentUser\\My.",bg="#101318",fg="#64748b",wraplength=800,justify="left").pack(anchor="w")
    def settings_tab(self):
        t=tk.Frame(self.nb,bg="#101318"); self.nb.add(t,text="Настройки")
        self.role=self.entry(t,"Роль","Производитель"); self.group=self.entry(t,"Товарная группа","Мясная продукция")
        tk.Label(t,text="Для API 3.0 заказ подписывается УКЭП. Закрытый ключ приложению не передаётся.",bg="#101318",fg="#64748b").pack(anchor="w",pady=20)
    def log_tab(self):
        t=tk.Frame(self.nb,bg="#101318"); self.nb.add(t,text="Журнал")
        self.log=tk.Text(t,bg="#0b0e12",fg="#cbd5e1",insertbackground="white",bd=0); self.log.pack(fill="both",expand=True,padx=8,pady=8)
    def write(self,m): self.logq.put(datetime.now().strftime("%H:%M:%S")+"  "+m)
    def drain(self):
        try:
            while True:self.log.insert("end",self.logq.get_nowait()+"\n"); self.log.see("end")
        except queue.Empty: pass
        self.after(150,self.drain)
    def base(self): return self.server.get().strip().rstrip("/")
    def common_headers(self):
        h={"Accept":"application/json","Content-Type":"application/json"}
        if self.token.get().strip(): h["clientToken"]=self.token.get().strip()
        return h
    def signed_post(self,path,payload):
        text=json.dumps(payload,ensure_ascii=False,separators=(",",":"))
        signer=CryptoProSigner(self.cert.get())
        sig=signer.sign(text)
        h=self.common_headers(); h["X-Signature"]=sig
        return self.http.post(self.base()+path,params={"omsId":self.oms.get().strip()},headers=h,data=text.encode("utf-8"),timeout=45)
    def ping(self):
        def run():
            try:
                r=self.http.get(self.base()+"/api/v3/ping",params={"omsId":self.oms.get().strip()},headers=self.common_headers(),timeout=20)
                self.write(f"PING: HTTP {r.status_code} {r.text[:500]}")
                self.state.config(text="● СУЗ доступен" if r.ok else "● Ошибка",fg="#22c55e" if r.ok else "#ef4444")
            except Exception as e:self.write("PING ошибка: "+str(e))
        threading.Thread(target=run,daemon=True).start()
    def create_order(self):
        try:q=int(self.qty.get())
        except: messagebox.showerror("Ошибка","Количество КМ должно быть целым."); return
        gtin=self.gtin.get().strip()
        if q<1 or not gtin: messagebox.showerror("Ошибка","Укажите количество и GTIN."); return
        product={"gtin":gtin,"quantity":q,"serialNumberType":"OPERATOR","cisType":"UNIT"}
        if self.template.get().strip():
            product["templateId"]=int(self.template.get())
        payload={"productGroup":GROUP,"products":[product],"attributes":{"releaseMethodType":"PRODUCTION","createMethodType":"SELF_MADE","paymentType":2 if self.payment.get()=="Оплата по нанесению" else 1}}
        self.result.config(text=json.dumps(payload,ensure_ascii=False,indent=2))
        threading.Thread(target=self._create,args=(payload,gtin),daemon=True).start()
    def _create(self,payload,gtin):
        try:
            r=self.signed_post("/api/v3/order",payload); self.write(f"ORDER: HTTP {r.status_code} {r.text[:1000]}")
            if r.ok:
                data=r.json(); self.last_order=data.get("orderId")
                self.after(0,lambda:messagebox.showinfo("Заказ принят",f"orderId: {self.last_order}"))
        except Exception as e:self.write("Ошибка заказа: "+str(e))
    def get_codes(self):
        if not self.last_order: messagebox.showwarning("Нет заказа","Сначала создайте заказ."); return
        gtin=self.gtin.get().strip()
        def run():
            try:
                p={"omsId":self.oms.get().strip(),"orderId":self.last_order,"gtin":gtin,"quantity":int(self.qty.get())}
                r=self.http.get(self.base()+"/api/v3/codes",params=p,headers=self.common_headers(),timeout=45)
                self.write(f"CODES: HTTP {r.status_code} {r.text[:1000]}")
                if not r.ok:return
                data=r.json()
                codes=data.get("codes") if isinstance(data,dict) else data
                if not isinstance(codes,list): codes=data.get("cis",[]) if isinstance(data,dict) else []
                self.after(0,lambda:self.fill_codes(codes,gtin))
            except Exception as e:self.write("Ошибка получения КМ: "+str(e))
        threading.Thread(target=run,daemon=True).start()
    def fill_codes(self,codes,gtin):
        for i in self.codes.get_children(): self.codes.delete(i)
        for c in codes:
            if isinstance(c,dict): c=c.get("cis") or c.get("code") or c.get("value") or ""
            if c:self.codes.insert("", "end",values=(c,gtin))
        self.nb.select(1)
    def export(self):
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p:return
        with open(p,"w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f,delimiter=";"); w.writerow(["Код маркировки","GTIN"])
            for i in self.codes.get_children(): w.writerow(self.codes.item(i,"values"))
        self.write("CSV сохранён: "+p)
if __name__=="__main__": App().mainloop()
