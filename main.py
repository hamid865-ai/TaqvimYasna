# -*- coding: utf-8 -*-
"""تقویم یسنا - نسخه موبایل اندروید با Kivy"""
import math, calendar
from datetime import date, datetime, timedelta
from kivy.app import App
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.clock import Clock

try:
    import jdatetime
except Exception:
    jdatetime = None
try:
    from hijri_converter import Gregorian
except Exception:
    Gregorian = None
try:
    import requests
except Exception:
    requests = None

CITIES = {
    'تهران': (35.6892,51.3890,3.5), 'مشهد': (36.2972,59.6067,3.5),
    'اصفهان': (32.6546,51.6680,3.5), 'شیراز': (29.5918,52.5837,3.5),
    'تبریز': (38.0962,46.2738,3.5), 'رشت': (37.2808,49.5832,3.5),
    'ساری': (36.5633,53.0601,3.5), 'نکا': (36.65,53.3,3.5),
    'قم': (34.6416,50.8746,3.5), 'کرج': (35.84,50.9391,3.5),
    'برلین': (52.52,13.405,1.0), 'لندن': (51.5072,-0.1276,0.0),
    'استانبول': (41.0082,28.9784,3.0), 'دبی': (25.2048,55.2708,4.0),
}
EVENTS = {(1,1):'نوروز',(1,2):'عید نوروز',(1,3):'عید نوروز',(1,4):'عید نوروز',
          (1,12):'روز جمهوری اسلامی',(1,13):'روز طبیعت',(2,1):'بزرگداشت سعدی',
          (2,25):'بزرگداشت فردوسی',(3,14):'رحلت امام خمینی (ره)',(3,15):'قیام ۱۵ خرداد',
          (9,30):'شب یلدا',(11,22):'پیروزی انقلاب اسلامی',(12,29):'ملی شدن صنعت نفت'}

def shamsi(g):
    if not jdatetime: return 'نیازمند نصب jdatetime'
    return jdatetime.date.fromgregorian(date=g).strftime('%Y/%m/%d')
def hijri(g):
    if not Gregorian: return 'نیازمند نصب hijri-converter'
    h=Gregorian(g.year,g.month,g.day).to_hijri(); return f'{h.year:04}/{h.month:02}/{h.day:02}'
def from_shamsi(s):
    if not jdatetime: raise ValueError('برای تبدیل شمسی کتابخانه jdatetime لازم است.')
    p=[int(x.strip()) for x in s.replace('-','/').split('/')]
    if len(p)!=3: raise ValueError('تاریخ را سال/ماه/روز وارد کنید.')
    return jdatetime.date(*p).togregorian()
def from_hijri(s):
    if not Gregorian: raise ValueError('برای تبدیل قمری کتابخانه hijri-converter لازم است.')
    p=[int(x.strip()) for x in s.replace('-','/').split('/')]
    if len(p)!=3: raise ValueError('تاریخ را سال/ماه/روز وارد کنید.')
    g=Gregorian.from_hijri(*p); return date(g.year,g.month,g.day)
def clockstr(m):
    m=int(round(m))%1440; return f'{m//60:02d}:{m%60:02d}'
def solar(day,lat,lon,offset):
    n=day.timetuple().tm_yday; out={}
    for name,t in [('طلوع',n+(6-lon/15)/24),('غروب',n+(18-lon/15)/24)]:
        m=.9856*t-3.289
        L=(m+1.916*math.sin(math.radians(m))+.020*math.sin(math.radians(2*m))+282.634)%360
        ra=math.degrees(math.atan(.91764*math.tan(math.radians(L))))%360
        ra+=(math.floor(L/90)*90)-(math.floor(ra/90)*90); ra/=15
        sd=.39782*math.sin(math.radians(L)); cd=math.cos(math.asin(sd))
        ch=(math.cos(math.radians(90.833))-sd*math.sin(math.radians(lat)))/(cd*math.cos(math.radians(lat)))
        if not -1<=ch<=1: out[name]='محاسبه‌نشد'; continue
        h=(360-math.degrees(math.acos(ch)) if name=='طلوع' else math.degrees(math.acos(ch)))/15
        utc=h+ra-.06571*t-6.622-lon/15
        out[name]=clockstr((utc+offset)*60)
    b=2*math.pi*(n-81)/364; eot=9.87*math.sin(2*b)-7.53*math.cos(b)-1.5*math.sin(b)
    noon=720-4*lon-eot+offset*60
    out['ظهر خورشیدی']=clockstr(noon)
    # تخمین فجر/عشاء و عصر
    dec=math.radians(23.45*math.sin(math.radians(360*(284+n)/365))); phi=math.radians(lat)
    def angle_time(alt,morning):
        ch=(math.sin(math.radians(alt))-math.sin(phi)*math.sin(dec))/(math.cos(phi)*math.cos(dec))
        if not -1<=ch<=1:return 'محاسبه‌نشد'
        return clockstr(noon+(-1 if morning else 1)*4*math.degrees(math.acos(ch)))
    out['فجر تقریبی']=angle_time(-18,True); out['عشاء تقریبی']=angle_time(-17,False)
    return out
def qibla(lat,lon):
    p=math.radians(lat); k=math.radians(21.4225); dl=math.radians(39.8262-lon)
    return (math.degrees(math.atan2(math.sin(dl), math.cos(p)*math.tan(k)-math.sin(p)*math.cos(dl)))+360)%360
def age(b,t):
    y=t.year-b.year; m=t.month-b.month; d=t.day-b.day
    if d<0:
        pm=t.month-1 or 12; py=t.year if t.month>1 else t.year-1
        d+=calendar.monthrange(py,pm)[1]; m-=1
    if m<0:m+=12;y-=1
    return y,m,d

class YasnaCalendar(App):
    title='تقویم یسنا'
    def build(self):
        self.lat,self.lon,self.offset= CITIES['تهران']; self.place='تهران (پیش‌فرض)'
        Window.clearcolor=(.95,.97,.99,1)
        root=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(7))
        header=BoxLayout(size_hint_y=None,height=dp(58),spacing=dp(8))
        self.clock=Label(text='',font_size='25sp',bold=True,color=(.02,.38,.48,1),size_hint_x=.48)
        header.add_widget(self.clock); header.add_widget(Label(text='تقویم یسنا',font_size='23sp',bold=True,color=(.08,.18,.28,1)))
        root.add_widget(header)
        self.status=Label(text='',size_hint_y=None,height=dp(34),font_size='12sp',color=(.15,.22,.3,1))
        root.add_widget(self.status)
        self.body=BoxLayout(orientation='vertical',spacing=dp(8))
        root.add_widget(self.body)
        nav=GridLayout(cols=3,size_hint_y=None,height=dp(54),spacing=dp(5))
        for title,fn in [('خانه و اوقات',self.home),('تبدیل تاریخ',self.converter),('سن',self.age_screen),('مکان و قبله',self.location),('رویدادها',self.events),('راهنما',self.help_screen)]:
            nav.add_widget(self.btn(title,fn,height=48))
        root.add_widget(nav)
        self.home(); Clock.schedule_interval(self.tick,1); return root
    def btn(self,text,fn,height=dp(44)):
        return Button(text=text,size_hint_y=None,height=dp(height) if isinstance(height,(int,float)) else height,
                      font_size='14sp',background_normal='',background_color=(.08,.39,.53,1),color=(1,1,1,1))
    def label(self,text,size=16,height=None,bold=False):
        return Label(text=text,font_size=f'{size}sp',bold=bold,color=(.08,.16,.24,1),size_hint_y=None if height else 1,height=dp(height) if height else 0,halign='center',valign='middle')
    def field(self,hint,text=''):
        return TextInput(hint_text=hint,text=text,multiline=False,size_hint_y=None,height=dp(46),font_size='16sp',halign='center')
    def show(self,widgets):
        self.body.clear_widgets()
        sv=ScrollView(do_scroll_x=False)
        box=BoxLayout(orientation='vertical',spacing=dp(9),padding=dp(5),size_hint_y=None)
        box.bind(minimum_height=box.setter('height'))
        for w in widgets: box.add_widget(w)
        sv.add_widget(box); self.body.add_widget(sv)
    def tick(self,dt):
        self.clock.text=datetime.now().strftime('%H:%M:%S')
    def update_status(self): self.status.text=f'مکان: {self.place} | {self.lat:.3f}, {self.lon:.3f} | UTC{self.offset:+g}'
    def home(self):
        g=date.today(); self.update_status(); st=solar(g,self.lat,self.lon,self.offset)
        widgets=[self.label('امروز',18,34,True),self.label('شمسی: '+shamsi(g),17,36,True),self.label('میلادی: '+g.strftime('%Y/%m/%d'),16,32),self.label('قمری: '+hijri(g),16,32),self.label('طلوع و غروب خورشید',18,35,True)]
        for k in ['طلوع','غروب','ظهر خورشیدی','فجر تقریبی','عشاء تقریبی']:
            widgets.append(self.label(f'{k}: {st.get(k,"—")}',16,32))
        widgets.append(self.label('اوقات شرعی تخمینی هستند؛ برای دقت مذهبی با تقویم معتبر محلی تطبیق دهید.',12,55))
        self.show(widgets)
    def converter(self):
        kind=Spinner(text='شمسی',values=('شمسی','میلادی','قمری'),size_hint_y=None,height=dp(45),font_size='15sp')
        inp=self.field('سال/ماه/روز؛ مانند 1405/07/29',shamsi(date.today()) if jdatetime else date.today().strftime('%Y/%m/%d'))
        result=self.label('نتیجه تبدیل در این قسمت نمایش داده می‌شود.',14,100)
        def run(*a):
            try:
                s=inp.text.strip()
                if kind.text=='شمسی': g=from_shamsi(s)
                elif kind.text=='قمری': g=from_hijri(s)
                else:
                    p=[int(x) for x in s.replace('-','/').split('/')]; g=date(*p)
                result.text=f'میلادی: {g:%Y/%m/%d}\nشمسی: {shamsi(g)}\nقمری: {hijri(g)}'
            except Exception as e: self.popup('خطا',str(e))
        year=self.field('سال شمسی برای تبدیل به میلادی','1405'); yr=self.label('',14,65)
        def yearrun(*a):
            try:
                y=int(year.text); start=jdatetime.date(y,1,1).togregorian(); end=jdatetime.date(y+1,1,1).togregorian()-timedelta(days=1)
                yr.text=f'سال {y} شمسی: از {start:%Y/%m/%d} تا {end:%Y/%m/%d} میلادی'
            except Exception as e:self.popup('خطا',str(e))
        self.show([self.label('تبدیل بین تقویم‌ها',18,35,True),kind,inp,self.btn('تبدیل تاریخ',run),result,self.label('تبدیل سال شمسی به بازه میلادی',17,38,True),year,self.btn('محاسبه بازه سال',yearrun),yr])
    def age_screen(self):
        kind=Spinner(text='شمسی',values=('شمسی','میلادی','قمری'),size_hint_y=None,height=dp(45),font_size='15sp')
        inp=self.field('تاریخ تولد: سال/ماه/روز')
        result=self.label('سن به سال، ماه و روز نمایش داده می‌شود.',14,100)
        def run(*a):
            try:
                if kind.text=='شمسی': b=from_shamsi(inp.text)
                elif kind.text=='قمری': b=from_hijri(inp.text)
                else:
                    p=[int(x) for x in inp.text.replace('-','/').split('/')]; b=date(*p)
                if b>date.today(): raise ValueError('تاریخ تولد نمی‌تواند در آینده باشد.')
                y,m,d=age(b,date.today()); result.text=f'سن: {y} سال، {m} ماه و {d} روز\nمیلادی: {b:%Y/%m/%d}\nشمسی: {shamsi(b)}\nقمری: {hijri(b)}'
            except Exception as e:self.popup('خطا',str(e))
        self.show([self.label('محاسبه سن',18,38,True),kind,inp,self.btn('محاسبه سن',run),result])
    def location(self):
        sp=Spinner(text='تهران',values=tuple(CITIES.keys()),size_hint_y=None,height=dp(45),font_size='15sp')
        lat=self.field('عرض جغرافیایی',str(self.lat)); lon=self.field('طول جغرافیایی',str(self.lon)); off=self.field('اختلاف ساعت با UTC',str(self.offset))
        result=self.label('',16,70,True)
        def city(*a):
            self.lat,self.lon,self.offset=CITIES[sp.text]; self.place=sp.text
            lat.text=str(self.lat);lon.text=str(self.lon);off.text=str(self.offset);self.update_status();calc()
        def calc(*a):
            try:
                self.lat=float(lat.text.replace(',','.'));self.lon=float(lon.text.replace(',','.'));self.offset=float(off.text.replace(',','.'))
                if not -90<=self.lat<=90 or not -180<=self.lon<=180 or not -12<=self.offset<=14: raise ValueError('مختصات یا اختلاف ساعت خارج از محدوده است.')
                self.place='مکان انتخابی'; self.update_status()
                result.text=f'جهت قبله: {qibla(self.lat,self.lon):.1f} درجه از شمال\nطلوع: {solar(date.today(),self.lat,self.lon,self.offset)["طلوع"]} | غروب: {solar(date.today(),self.lat,self.lon,self.offset)["غروب"]}'
            except Exception as e:self.popup('خطا',str(e))
        def locate(*a):
            if not requests:self.popup('نیاز به اینترنت','کتابخانه requests در دسترس نیست. شهر را دستی انتخاب کنید.');return
            box=BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(10))
            box.add_widget(Label(text='برای یافتن مکان تقریبی، IP شما به سرویس اینترنتی ارسال می‌شود. ادامه می‌دهید؟',font_size='15sp'))
            row=BoxLayout(size_hint_y=None,height=dp(45),spacing=dp(8)); pop=Popup(title='اجازه مکان‌یابی',content=box,size_hint=(.9,.42))
            yes=Button(text='ادامه'); no=Button(text='انصراف'); row.add_widget(yes);row.add_widget(no);box.add_widget(row)
            def do_lookup(*args):
                pop.dismiss()
                try:
                    d=requests.get('https://ipapi.co/json/',timeout=6).json(); self.lat=float(d['latitude']);self.lon=float(d['longitude'])
                    tz=d.get('utc_offset','+00:00'); self.offset=(1 if tz[0]=='+' else -1)*(int(tz[1:3])+int(tz[4:6])/60)
                    self.place=d.get('city') or d.get('region') or 'مکان تقریبی اینترنت';lat.text=str(self.lat);lon.text=str(self.lon);off.text=str(self.offset)
                    self.update_status();calc()
                except Exception as e:self.popup('مکان‌یابی ناموفق',str(e))
            yes.bind(on_release=do_lookup);no.bind(on_release=pop.dismiss);pop.open()
        self.show([self.label('انتخاب شهر یا مختصات',18,38,True),sp,self.btn('انتخاب شهر',city),lat,lon,off,self.btn('ثبت مختصات و محاسبه قبله',calc),self.btn('تشخیص تقریبی مکان با اینترنت',locate),result,self.label('این جهت‌نما زاویه قبله را محاسبه می‌کند؛ برای قطب‌نمای زنده به حسگر قطب‌نما نیاز است.',12,60)])
        city()
    def events(self):
        yr=self.field('سال شمسی','1405'); result=self.label('',14,360)
        def run(*a):
            try:
                y=int(yr.text); lines=[f'رویدادهای نمونه سال {y} شمسی','']
                for (m,d),name in sorted(EVENTS.items()): lines.append(f'{d:02}/{m:02} — {name}')
                lines += ['', 'فهرست نمونه است؛ مناسبت‌های قمری و تعطیلات رسمی هر سال باید با تقویم رسمی تطبیق داده شوند.'];result.text='\n'.join(lines)
            except Exception as e:self.popup('خطا',str(e))
        run();self.show([self.label('رویدادهای سالانه',18,38,True),yr,self.btn('نمایش رویدادها',run),result])
    def help_screen(self):
        self.show([self.label('درباره تقویم یسنا',19,40,True),self.label('نسخه موبایل آزمایشی\n\n• ساعت زنده\n• تبدیل تاریخ شمسی، میلادی و قمری\n• محاسبه سن\n• طلوع و غروب خورشید و اوقات تقریبی\n• محاسبه جهت قبله\n• انتخاب شهر و مکان‌یابی تقریبی با اجازه شما\n• فهرست اولیه رویدادهای سالانه\n\nبرای تبدیل تقویم باید کتابخانه‌های همراه برنامه نصب باشند. مکان‌یابی IP تقریبی است و GPS واقعی نیست.',15,360)])
    def popup(self,title,msg):
        box=BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(10)); box.add_widget(Label(text=msg,font_size='15sp'))
        b=Button(text='باشه',size_hint_y=None,height=dp(45)); box.add_widget(b); p=Popup(title=title,content=box,size_hint=(.88,.45)); b.bind(on_release=p.dismiss);p.open()
    def confirm(self,title,msg):
        box=BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(10));box.add_widget(Label(text=msg,font_size='15sp'))
        row=BoxLayout(size_hint_y=None,height=dp(45),spacing=dp(8)); answer={'yes':False}; p=Popup(title=title,content=box,size_hint=(.9,.45))
        y=Button(text='ادامه'); n=Button(text='انصراف');row.add_widget(y);row.add_widget(n);box.add_widget(row)
        y.bind(on_release=lambda *_:(answer.update(yes=True),p.dismiss()));n.bind(on_release=p.dismiss);p.open()
        # Popup nonblocking; callers should use dedicated UI confirmation instead.
        return False

if __name__=='__main__': YasnaCalendar().run()
