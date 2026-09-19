import base64, csv, json, os, queue, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import requests

APP_TITLE="Честный ЗНАК — СУЗ API 3.0"
DEFAULT_GROUP="Мясная продукция"

class ContextMenu:
    def __init__(self,w):
        self.w=w
        m=tk.Menu(w,tearoff=0)
        m.add_command(label="Вырезать",command=lambda:w.event_generate("<<Cut>>"))
        m.add_command(label="Копировать",command=lambda:w.event_generate("<<Copy>>"))
        m.add_command(label="Вставить",command=lambda:w.event_generate("<<Paste>>"))
        m.add_separator(); m.add_command(label="Выделить всё",command=lambda:w.event_generate("<<SelectAll>>"))
        w.bind("<Button-3>",lambda e:self.popup(m,e.x_root,e.y_root))
        w.bind("<Control-a>",lambda e:(w.event_generate("<<SelectAll>>"),"break")[1])
    def popup(self,m,x,y): m.tk_popup(x,y)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE); self.geometry("1100x720"); self.minsize(950,620)
        self.configure(bg="#101318")
        self.s=requests.Session(); self.logq=queue.Queue(); self.settings={}
        self._style(); self._ui(); self.after(150,self._drain_log)

    def _style(self):
        st=ttk.Style(self); st.theme_use("clam")
        st.configure("TNotebook",background="#101318",borderwidth=0)
        st.configure("TNotebook.Tab",background="#1b2028",foreground="#cbd5e1",padding=(18,9))
        st.map("TNotebook.Tab",background=[("selected","#2563eb")],foreground=[("selected","white")])
        st.configure("TEntry",fieldbackground="#171b22",foreground="white",insertcolor="white")
        st.configure("TCombobox",fieldbackground="#171b22",foreground="white")
        st.configure("TButton",background="#2563eb",foreground="white",padding=8)
        st.configure("Treeview",background="#171b22",foreground="#e5e7eb",fieldbackground="#171b22",rowheight=28)
        st.configure("Treeview.Heading",background="#242a33",foreground="white")

    def _ui(self):
        side=tk.Frame(self,bg="#151922",width=220); side.pack(side="left",fill="y")
        tk.Label(side,text="ЧЕСТНЫЙ ЗНАК",bg="#151922",fg="white",font=("Segoe UI",17,"bold")).pack(pady=(30,2))
        tk.Label(side,text="СУЗ API 3.0",bg="#151922",fg="#60a5fa",font=("Segoe UI",10)).pack(pady=(0,25))
        for name,cmd in [("Заказ кодов",lambda:self.nb.select(0)),("Полученные КМ",lambda:self.nb.select(1)),("Подключение",lambda:self.nb.select(2)),("Настройки",lambda:self.nb.select(3)),("Журнал",lambda:self.nb.select(4))]:
            tk.Button(side,text=name,command=cmd,anchor="w",bd=0,bg="#151922",fg="#d1d5db",activebackground="#2563eb",activeforeground="white",font=("Segoe UI",11),padx=25,pady=11).pack(fill="x")
        self.status=tk.Label(side,text="● Не подключено",bg="#151922",fg="#f59e0b",font=("Segoe UI",9)); self.status.pack(side="bottom",pady=25)

        main=tk.Frame(self,bg="#101318"); main.pack(side="left",fill="both",expand=True,padx=22,pady=20)
        self.nb=ttk.Notebook(main); self.nb.pack(fill="both",expand=True)
        self._order_tab(); self._codes_tab(); self._conn_tab(); self._settings_tab(); self._log_tab()

    def _label_entry(self,parent,label,default=""):
        f=tk.Frame(parent,bg="#101318"); f.pack(fill="x",pady=6)
        tk.Label(f,text=label,bg="#101318",fg="#aab2bf",font=("Segoe UI",9)).pack(anchor="w")
        e=ttk.Entry(f); e.insert(0,default); e.pack(fill="x",pady=(3,0)); ContextMenu(e); return e

    def _order_tab(self):
        tab=tk.Frame(self.nb,bg="#101318"); self.nb.add(tab,text="Заказ кодов")
        tk.Label(tab,text="Новый заказ",bg="#101318",fg="white",font=("Segoe UI",20,"bold")).pack(anchor="w",pady=(20,18))
        box=tk.Frame(tab,bg="#171b22"); box.pack(fill="x",padx=10,pady=5)
        self.qty=self._label_entry(box,"Количество кодов","100")
        self.gtin=self._label_entry(box,"GTIN","")
        self.product=self._label_entry(box,"Наименование товара","")
        self.payment=tk.StringVar(value="Оплата по нанесению")
        f=tk.Frame(box,bg="#171b22"); f.pack(fill="x",pady=6)
        tk.Label(f,text="Оплата",bg="#171b22",fg="#aab2bf").pack(anchor="w")
        ttk.Combobox(f,textvariable=self.payment,state="readonly",values=["Оплата по нанесению","Оплата по эмиссии"]).pack(fill="x",pady=3)
        tk.Button(tab,text="ОФОРМИТЬ ЗАКАЗ",command=self.create_order,bg="#2563eb",fg="white",bd=0,font=("Segoe UI",11,"bold"),padx=20,pady=12).pack(anchor="e",pady=20)
        self.order_result=tk.Label(tab,text="",bg="#101318",fg="#94a3b8",justify="left"); self.order_result.pack(anchor="w")

    def _codes_tab(self):
        tab=tk.Frame(self.nb,bg="#101318"); self.nb.add(tab,text="Полученные КМ")
        self.codes=ttk.Treeview(tab,columns=("code","gtin"),show="headings"); self.codes.heading("code",text="Код маркировки"); self.codes.heading("gtin",text="GTIN"); self.codes.column("code",width=720); self.codes.pack(fill="both",expand=True,pady=15)
        tk.Button(tab,text="Экспорт CSV",command=self.export_csv,bg="#2563eb",fg="white",bd=0,padx=16,pady=9).pack(anchor="e")

    def _conn_tab(self):
        tab=tk.Frame(self.nb,bg="#101318"); self.nb.add(tab,text="Подключение")
        self.server=self._label_entry(tab,"Адрес СУЗ","")
        self.oms=self._label_entry(tab,"OMS ID","")
        self.token=self._label_entry(tab,"Client Token","")
        self.cert=self._label_entry(tab,"Сертификат CryptoPro (thumbprint)","")
        tk.Button(tab,text="Сохранить и проверить",command=self.test_connection,bg="#2563eb",fg="white",bd=0,padx=18,pady=10).pack(anchor="e",pady=18)
        tk.Label(tab,text="ИНН здесь не вводится: авторизация выполняется средствами СУЗ/сертификата.",bg="#101318",fg="#64748b").pack(anchor="w")

    def _settings_tab(self):
        tab=tk.Frame(self.nb,bg="#101318"); self.nb.add(tab,text="Настройки")
        self.role=self._label_entry(tab,"Роль организации","Производитель")
        self.group=self._label_entry(tab,"Товарная группа",DEFAULT_GROUP)
        self.address=self._label_entry(tab,"Идентификатор соединения","")
        tk.Label(tab,text="CryptoPro/CAdESCOM должен быть установлен в Windows. Закрытый ключ из приложения не извлекается.",bg="#101318",fg="#64748b",wraplength=750,justify="left").pack(anchor="w",pady=20)

    def _log_tab(self):
        tab=tk.Frame(self.nb,bg="#101318"); self.nb.add(tab,text="Журнал")
        self.log=tk.Text(tab,bg="#0b0e12",fg="#cbd5e1",insertbackground="white",bd=0); self.log.pack(fill="both",expand=True,padx=8,pady=8)

    def write_log(self,msg):
        self.logq.put(datetime.now().strftime("%H:%M:%S")+"  "+msg)

    def _drain_log(self):
        try:
            while True:self.log.insert("end",self.logq.get_nowait()+"\n"); self.log.see("end")
        except queue.Empty: pass
        self.after(150,self._drain_log)

    def base(self):
        return self.server.get().strip().rstrip("/")

    def headers(self):
        h={"Accept":"application/json","Content-Type":"application/json"}
        if self.token.get().strip(): h["Client-Token"]=self.token.get().strip()
        return h

    def test_connection(self):
        def work():
            try:
                r=self.s.get(self.base(),headers=self.headers(),timeout=15)
                self.write_log(f"Проверка СУЗ: HTTP {r.status_code}")
                self.status.config(text="● Подключено",fg="#22c55e")
            except Exception as e:
                self.write_log("Ошибка подключения: "+str(e)); self.status.config(text="● Ошибка",fg="#ef4444")
        threading.Thread(target=work,daemon=True).start()

    def create_order(self):
        try:q=int(self.qty.get())
        except: messagebox.showerror("Ошибка","Количество должно быть целым."); return
        if q<1: messagebox.showerror("Ошибка","Количество должно быть больше нуля."); return
        payload={"productGroup":"meat","quantity":q}
        if self.gtin.get().strip(): payload["gtin"]=self.gtin.get().strip()
        if self.product.get().strip(): payload["productName"]=self.product.get().strip()
        payload["paymentType"]="BY_APPLICATION" if self.payment.get()=="Оплата по нанесению" else "BY_EMISSION"
        self.write_log("Подготовлен заказ API 3.0. Отправка...")
        self.order_result.config(text=json.dumps(payload,ensure_ascii=False,indent=2))
        threading.Thread(target=self._post_order,args=(payload,),daemon=True).start()

    def _post_order(self,payload):
        try:
            url=self.base()+"/api/v3/orders"
            body=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode()
            r=self.s.post(url,data=body,headers=self.headers(),timeout=30)
            self.write_log(f"Заказ: HTTP {r.status_code} {r.text[:500]}")
            if r.ok:
                messagebox.showinfo("Готово","Заказ принят СУЗ.")
        except Exception as e:self.write_log("Ошибка заказа: "+str(e))

    def export_csv(self):
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p:return
        with open(p,"w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f,delimiter=";"); w.writerow(["Код маркировки","GTIN"])
            for i in self.codes.get_children():
                v=self.codes.item(i,"values"); w.writerow(v)
        self.write_log("CSV сохранён: "+p)

if __name__=="__main__":
    App().mainloop()
