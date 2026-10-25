#!/usr/bin/env python3
"""
PROTON ORBIT — a mission-control TUI for the Proton VPN Linux CLI.

This is a single-file Textual application.  It intentionally talks to the
installed `protonvpn` command for every VPN operation (connect, disconnect,
status, sign-in/out, countries, cities, configuration), and adds a few
TUI-only conveniences such as the animated world map and AutoConnect region
exclusions.

Requirements:
    python >= 3.10
    textual >= 8
    rich >= 13
    protonvpn CLI installed and available in PATH

Run:
    python3 proton_orbit.py
    # or set a different CLI binary:
    PROTONVPN_BIN=/path/to/protonvpn python3 proton_orbit.py

Embedded map data is derived from Natural Earth 1:110m (public domain) and is
compressed into this file.  No third-party map service is required.
"""
from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
import zlib
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.request import Request, urlopen

try:
    from rich.markup import escape as markup_escape
    from rich.style import Style
    from rich.text import Text
except ImportError:  # pragma: no cover - friendly startup error
    print("PROTON ORBIT requires 'rich'. Install it with: pip install rich textual")
    raise

try:
    from textual import events, on
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import (
        Grid,
        Horizontal,
        Vertical,
        VerticalScroll,
    )
    from textual.message import Message
    from textual.screen import ModalScreen, Screen
    from textual.widget import Widget
    from textual.widgets import Button, Input, OptionList, Select, Static
    from textual.widgets.option_list import Option
except ImportError:  # pragma: no cover - friendly startup error
    print("PROTON ORBIT requires 'textual'. Install it with: pip install 'textual>=8'")
    raise


# ===========================================================================
# Embedded geography
# ===========================================================================

# Auto-generated from Natural Earth 110m + protonvpn countries list.
LAND_W, LAND_H = 1440, 720
COUNTRIES = {
    'AD': ('Andorra', 42.508, 1.521, ''),
    'AE': ('United Arab Emirates', 23.466, 54.547, 'Asia'),
    'AF': ('Afghanistan', 34.164, 66.497, 'Asia'),
    'AL': ('Albania', 40.655, 20.114, 'Europe'),
    'AM': ('Armenia', 40.459, 44.801, 'Asia'),
    'AO': ('Angola', -12.183, 17.984, 'Africa'),
    'AR': ('Argentina', -33.501, -64.173, 'South America'),
    'AT': ('Austria', 47.519, 14.131, 'Europe'),
    'AU': ('Australia', -24.13, 134.05, 'Oceania'),
    'AZ': ('Azerbaijan', 40.402, 47.211, 'Asia'),
    'BA': ('Bosnia and Herzegovina', 44.091, 18.068, 'Europe'),
    'BD': ('Bangladesh', 24.215, 89.685, 'Asia'),
    'BE': ('Belgium', 50.785, 4.8, 'Europe'),
    'BG': ('Bulgaria', 42.509, 25.157, 'Europe'),
    'BH': ('Bahrain', 26.229, 50.586, ''),
    'BN': ('Brunei', 4.448, 114.552, 'Asia'),
    'BO': ('Bolivia', -16.666, -64.593, 'South America'),
    'BR': ('Brazil', -12.099, -49.559, 'South America'),
    'BT': ('Bhutan', 27.537, 90.04, 'Asia'),
    'BY': ('Belarus', 53.822, 28.418, 'Europe'),
    'CA': ('Canada', 60.324, -101.911, 'North America'),
    'CD': ('Democratic Republic of the Congo', -1.858, 23.459, 'Africa'),
    'CH': ('Switzerland', 46.719, 7.464, 'Europe'),
    'CI': ('Ivory Coast', 7.491, -5.569, 'Africa'),
    'CL': ('Chile', -38.152, -72.319, 'South America'),
    'CM': ('Cameroon', 4.585, 12.473, 'Africa'),
    'CN': ('China', 32.498, 106.337, 'Asia'),
    'CO': ('Colombia', 3.373, -73.174, 'South America'),
    'CR': ('Costa Rica', 10.065, -84.078, 'North America'),
    'CU': ('Cuba', 21.334, -77.976, 'North America'),
    'CY': ('Cyprus', 34.913, 33.084, 'Asia'),
    'CZ': ('Czech Republic', 49.882, 15.378, 'Europe'),
    'DE': ('Germany', 50.962, 9.678, 'Europe'),
    'DK': ('Denmark', 55.967, 9.018, 'Europe'),
    'DO': ('Dominican Republic', 19.104, -70.654, 'North America'),
    'DZ': ('Algeria', 27.397, 2.808, 'Africa'),
    'EC': ('Ecuador', -1.259, -78.188, 'South America'),
    'EE': ('Estonia', 58.725, 25.867, 'Europe'),
    'EG': ('Egypt', 26.186, 29.446, 'Africa'),
    'ER': ('Eritrea', 15.787, 38.286, 'Africa'),
    'ES': ('Spain', 40.091, -3.465, 'Europe'),
    'ET': ('Ethiopia', 8.033, 39.089, 'Africa'),
    'FI': ('Finland', 63.252, 27.276, 'Europe'),
    'FR': ('France', 46.696, 2.552, 'Europe'),
    'GA': ('Gabon', -0.438, 11.836, 'Africa'),
    'GE': ('Georgia', 41.87, 43.736, 'Asia'),
    'GH': ('Ghana', 7.718, -1.037, 'Africa'),
    'GL': ('Greenland', 74.319, -39.335, 'North America'),
    'GN': ('Guinea', 10.619, -10.016, 'Africa'),
    'GR': ('Greece', 39.493, 21.726, 'Europe'),
    'GT': ('Guatemala', 14.982, -90.497, 'North America'),
    'HK': ('Hong Kong', 22.319, 114.169, ''),
    'HN': ('Honduras', 14.795, -86.888, 'North America'),
    'HR': ('Croatia', 45.806, 16.372, 'Europe'),
    'HT': ('Haiti', 19.264, -72.224, 'North America'),
    'HU': ('Hungary', 47.087, 19.448, 'Europe'),
    'ID': ('Indonesia', -0.954, 101.893, 'Asia'),
    'IE': ('Ireland', 53.079, -7.799, 'Europe'),
    'IL': ('Israel', 30.911, 34.848, 'Asia'),
    'IN': ('India', 22.687, 79.358, 'Asia'),
    'IQ': ('Iraq', 33.094, 43.262, 'Asia'),
    'IS': ('Iceland', 64.779, -18.674, 'Europe'),
    'IT': ('Italy', 44.732, 11.077, 'Europe'),
    'JM': ('Jamaica', 18.137, -77.319, 'North America'),
    'JO': ('Jordan', 30.805, 36.376, 'Asia'),
    'JP': ('Japan', 36.143, 138.442, 'Asia'),
    'KE': ('Kenya', 0.549, 37.908, 'Africa'),
    'KG': ('Kyrgyzstan', 41.669, 74.533, 'Asia'),
    'KH': ('Cambodia', 12.648, 104.505, 'Asia'),
    'KM': ('Comoros', -11.717, 43.255, ''),
    'KR': ('South Korea', 36.385, 128.13, 'Asia'),
    'KW': ('Kuwait', 29.414, 47.314, 'Asia'),
    'KZ': ('Kazakhstan', 49.054, 68.686, 'Asia'),
    'LA': ('Laos', 19.432, 102.534, 'Asia'),
    'LB': ('Lebanon', 34.133, 35.993, 'Asia'),
    'LI': ('Liechtenstein', 47.141, 9.521, ''),
    'LK': ('Sri Lanka', 7.581, 80.705, 'Asia'),
    'LT': ('Lithuania', 55.104, 24.09, 'Europe'),
    'LU': ('Luxembourg', 49.734, 6.078, 'Europe'),
    'LV': ('Latvia', 57.067, 25.459, 'Europe'),
    'LY': ('Libya', 26.639, 18.011, 'Africa'),
    'MA': ('Morocco', 31.651, -7.187, 'Africa'),
    'MC': ('Monaco', 43.738, 7.425, ''),
    'MD': ('Moldova', 47.435, 28.488, 'Europe'),
    'ME': ('Montenegro', 42.803, 19.144, 'Europe'),
    'MK': ('Macedonia', 41.558, 21.556, 'Europe'),
    'MM': ('Myanmar', 21.574, 95.804, 'Asia'),
    'MN': ('Mongolia', 45.997, 104.15, 'Asia'),
    'MO': ('Macao', 22.199, 113.544, ''),
    'MR': ('Mauritania', 19.587, -9.74, 'Africa'),
    'MT': ('Malta', 35.899, 14.515, ''),
    'MU': ('Mauritius', -20.161, 57.501, ''),
    'MX': ('Mexico', 23.92, -102.289, 'North America'),
    'MY': ('Malaysia', 2.529, 113.837, 'Asia'),
    'MZ': ('Mozambique', -13.943, 37.838, 'Africa'),
    'NG': ('Nigeria', 9.44, 7.503, 'Africa'),
    'NI': ('Nicaragua', 12.671, -85.069, 'North America'),
    'NL': ('Netherlands', 52.422, 5.611, 'Europe'),
    'NO': ('Norway', 61.357, 9.68, 'Europe'),
    'NP': ('Nepal', 28.298, 83.64, 'Asia'),
    'NZ': ('New Zealand', -39.759, 172.787, 'Oceania'),
    'OM': ('Oman', 22.12, 57.337, 'Asia'),
    'PA': ('Panama', 8.722, -80.352, 'North America'),
    'PE': ('Peru', -12.977, -72.9, 'South America'),
    'PG': ('Papua New Guinea', -5.695, 143.91, 'Oceania'),
    'PH': ('Philippines', 11.198, 122.465, 'Asia'),
    'PK': ('Pakistan', 29.328, 68.546, 'Asia'),
    'PL': ('Poland', 51.99, 19.49, 'Europe'),
    'PR': ('Puerto Rico', 18.235, -66.481, 'North America'),
    'PS': ('Palestinian Territory', 32.047, 35.291, 'Asia'),
    'PT': ('Portugal', 39.607, -8.272, 'Europe'),
    'PY': ('Paraguay', -21.675, -60.146, 'South America'),
    'QA': ('Qatar', 25.237, 51.144, 'Asia'),
    'RO': ('Romania', 45.733, 24.973, 'Europe'),
    'RS': ('Serbia', 44.19, 20.788, 'Europe'),
    'RU': ('Russia', 58.249, 44.686, 'Europe'),
    'RW': ('Rwanda', -1.897, 30.104, 'Africa'),
    'SA': ('Saudi Arabia', 23.807, 44.7, 'Asia'),
    'SD': ('Sudan', 16.331, 29.261, 'Africa'),
    'SE': ('Sweden', 65.859, 19.017, 'Europe'),
    'SG': ('Singapore', 1.352, 103.82, ''),
    'SI': ('Slovenia', 46.061, 14.915, 'Europe'),
    'SK': ('Slovakia', 48.734, 19.05, 'Europe'),
    'SN': ('Senegal', 15.138, -14.779, 'Africa'),
    'SO': ('Somalia', 3.569, 45.192, 'Africa'),
    'SS': ('South Sudan', 7.23, 30.39, 'Africa'),
    'SV': ('El Salvador', 13.685, -88.89, 'North America'),
    'SY': ('Syria', 35.007, 38.278, 'Asia'),
    'TD': ('Chad', 15.143, 18.645, 'Africa'),
    'TG': ('Togo', 8.807, 1.058, 'Africa'),
    'TH': ('Thailand', 15.46, 101.073, 'Asia'),
    'TJ': ('Tajikistan', 38.2, 72.587, 'Asia'),
    'TM': ('Turkmenistan', 39.855, 58.677, 'Asia'),
    'TN': ('Tunisia', 33.687, 9.008, 'Africa'),
    'TR': ('Turkey', 39.345, 34.508, 'Asia'),
    'TW': ('Taiwan', 23.652, 120.868, 'Asia'),
    'TZ': ('Tanzania', -6.052, 34.959, 'Africa'),
    'UA': ('Ukraine', 49.725, 32.141, 'Europe'),
    'UG': ('Uganda', 1.973, 32.949, 'Africa'),
    'UK': ('United Kingdom', 54.403, -2.116, 'Europe'),
    'US': ('United States', 39.538, -97.483, 'North America'),
    'UY': ('Uruguay', -32.961, -55.967, 'South America'),
    'UZ': ('Uzbekistan', 41.694, 64.005, 'Asia'),
    'VE': ('Venezuela', 7.182, -64.599, 'South America'),
    'VN': ('Vietnam', 21.715, 105.387, 'Asia'),
    'XK': ('Kosovo', 42.594, 20.861, 'Europe'),
    'YE': ('Yemen', 15.328, 45.874, 'Asia'),
    'ZA': ('South Africa', -29.709, 23.666, 'Africa'),
    'ZW': ('Zimbabwe', -18.912, 29.925, 'Africa'),
}

LAND_MASK_B85 = (
    'c-rlqOOG8lc7Vxd$JK)vs@}yxgsvWBk*%`RLJ@mbS^6i$yDZ}Yvd}`KqN0Vo2;lsJ(fkYt2q4M|psb?#0RddL2JuqV7>FpCstT)$'
    '^<dpwEWYY?-=ye`CEdq&S%-&*hvxynHny>iZERy3+t|i7wy}+EY-1bS*v2-Fb0k$g*ikWO4Rb|rHeN-Bzrs~FZYDD7`RMdl$Wh)z'
    '<on40sAf8?MuXoxWR0(3KGFV8+&E%5Cazd5CLpiU(T_O0am@J`x$LAw<oZ058^w&r%mu3UjO2#N^ob@L6G>6??62|QI(r=%NdeO('
    'Wjv_gS}9hM3_21Hg6EJIL?e4m_HR{u9i>t9b6aF{$a}Vxt8;A|-MjIuvWYfJ?yKg*>uJudr#aE}c2><P{$d@|?RB@-U}Y)IXXu^2'
    '*<d!Olf*jn{A0fY!JIr#BuXS@ZZn6OZgxf71mE|_bIj%LHbiY?HI2=D+1nb=dP^g>5@+1V#hIPxftZH|Ox4n6Stqh{qEYOzwhK$U'
    'Jc(w?KBxhC!ohf&vE>p>?X7B9WwBI8A~9ekmy+Zxv6{=wR&78R`vb>P9dd%3=T_0QVoEvBBkye7c`Z<uavIINN}A_|A2-%9Y9BSW'
    'XO_ZIq{31-NVGF+^GR2KDWww8yb)(;&n#a`6FWKmBo6R7ln=N2a@w+%`muG%sKfHHSc~aZ1m@aI?#*Yludtnip?2chnP*{*0%L3|'
    'Xr!hR(W>Z*m{i^FD$0bz*A+2jx$Ga96bG7j>UnmWcXctG)df3~n#ORS<;`a_6IDu;!EiT|Fv1xn*#WGXL)D$cl%@tM8*4yXIs*4t'
    'x!)m0-yrE;uNn#Tzz|fM%4ZETzzxvp$Pv0{5bM>gzc#JlKEF;T-0iufIg*fuIjz6sZ1TOH%-M9Bv%MdIe6~jU2sv(<&*cA;bS#94'
    'H#3}Cd-?uTgO|GmtCf{jPpYq{ADMVB!fc{nl9`iEJ^L&t9`3HPp6{pfzgWy@qSVs4U8%Nj3is1(+G0po;>(?<zjz#+7Y#5Y%#(kq'
    'XTjZe>g6eK8Ou2bo`XEYiIC>A+VWgk4Q?}>Yu}~2J+sBL)%-aE%qSod?9mu~_MX#P;=Kgt9j-;NcR=(;-DPv~Atxt$FIU_yRP>ik'
    '_EfHkLPlII(RM}1qe@!)>ZE5M<Y_hM__w~CK$_4_7sba~b@awaUbuUXeqRfADd*x{eMl-(>HaDVii6vIFf%XYnz<azZ^sLt4{}z~'
    'M=mAsMeV;8S@mZ8VDklw->5#-aRTqNw9;O%OXu6mv^)WitILzdgaNtqz40+K_A={or5vQd-JL%_FrU*Ft{UgS6V}|F2st_Rw2DhI'
    'uQ==`B`>@AF77QbyUK<neAP^zd`$KA6lug)q<m)6m9M;S_raojkn94LnaLD)^-D|UuiMKsCO=->@6`mI-Bf<C)B7XltoLc}-JKH0'
    '8)^CChN*1UvB(JAF$r=XdG2(Al#1dvy?=Pm_H@<l0Fw`3#?Qtbij=Fo=v5n>({;k-G%u&%iJ159Fd%oAC;N8S(VtKEtd+b&xnCPg'
    'J4V4-?qSv;^?v!>Qv)-HGmmd<t?b-%V4?(8G~Xn^u2G;1^xJCokVdpGEtFn*IgebGsM>#%K5|RR8@kC?o_7XCsh(&)-8<0t+SmLv'
    'XO-pJRH?mNGJjuLk6}VHZ67XoRQRANYR5q~eOeR!OlO$kR3<MJbCFv!iy4Dx{4cN=SslEU!eqL6O!PC^ziXYMz2BKtokQDd7-Dv)'
    '`raq(WHgZ+qGqZlt1z|N2lM^5eCok`HFJ#Y?g?&58x;2eCan2~yput?ckeFdgKG*hy$X|WerJzds-Iu(Wo`wbD(_1tPWRU=6}W7+'
    '-OKjx3dNi*t2(^T=9Awo-}=UdIVTWkiZ847#W{2mT!K0-Mw~Yu^khVEFIzT6_x_-~xs`Fy8|~A@<A*t3z~!LLU#M?v3}|szzN~1?'
    '4!%!8lld6OspLpo1GqCc;S7Sz9FqE}ld2WM5}e2=8BsRO=@>6tT!Gn+x<VA3%MX!4!!kE!o)3=`&8tOB+Ypv3Bu{Ffc|$r9D!eEf'
    '`S>}Us&i@W7A{id9d;chFkX+;-;>sa32#Ev8inzA*do$JM*-A+6q3ISs*o{hHI}&#v-%=z*nS%C8me$B=<+wz{{C`DG=wQ+x0@i?'
    '_$!C^WM0hNJke5oNuxKayfs_ocQ#VUC%?5^h>2AbR25?bR-~1`a3I4g-e}=-^0J$y{j}mmb6*e2gZkFTz2vzQ4!hTW*GxQ1dUcyG'
    'x(PIi<*3xYiTNR`3A0`dwXh7@ZqZW*CxTc)-4OH}@0)K=T}+j%-$C$_KNC%uvBvz^lliAw{i2sHPbJ^OJQG7Xs14ruhV(eutnwYa'
    'K1SKSw2h1yD06)Y=HNULGZE9ZBojW_u)LYe`Rl&DMr{3f;e=VOWcqLtL@=VF?Y<N~o|=O{XBDIJA!F?yU~LeKUA56(Ix}#UMqz%f'
    'pURh{nRWB5Ze>$#LqWTn%gCf<4%*2$erUXSw)4#Y*kRB%$SBd32ApaTIFdaEU=-wfHx>4p?p+_)!w?-*S*an?sjB0O`3%HiCJnRg'
    '8vI^<e}_p1W}!*Kj@sbub7Yvtk&QM023e}g7lV$Wqis%%5z8G5Njacc7H66Z6;pC{W;F$<xfcB}9F!)^U}`Ki6D*KA2Un4%dB*)c'
    '>q7ev>0`iyO{6oU=_amC@Yk`HVCU#a?e?D6LTQUJGarXe>{=U<#8^8DKdLV+GaFkYlNPit0{O&t)~C6h2vEgmw$&V>4$?i-Z)owv'
    'c0S$Rxdn{N+<Y72cFK<T{<6G!#z!+rjfr~<#bxHob7#w3`_UT}_GaYGEzS9nG>OYBT(m|r!=#CnulV_LfU}Ybkgmg=*}hhQ7ZoM-'
    '75Jddgi$mcEZv3gZ`BVyo4GWbm3>xUNAUViXn3bEW=KY3<`bWUwT=PsMe{y5QVnL;h5(V)Ak!U{(B7#4sjevS{5(fxMy(Uo5Y%9b'
    'U)7njC1xIlS%wL~$@Yc2Gq}-g9ps3P57yi$&vE9Nz}C_#c9`GV*i$+)ns*_^T!Zo+E#03A|GYxW(b)N9=UZT|Vlda?Te+@Q(W@2<'
    '8|;}0^I%xu!pvO9s!$wkW7OjObSxS#I;}mwX^HVOq2ShlRv4>A$nV26bT2I0g#$;=H>KU>iFyXh%ony5F68%}+n?;`*T1~UxSHH;'
    'w{A*0Z+i$`Hn24_t#_b2_-um3`96CFJTzQXXou?pSVScc%we<4n+U<(Z2*q$*fS%uQj->;q4Jek^IVfKskls<NS)nn;KQJ>6JrEL'
    'qOLs)3+Cp&1cWd*+A3lDQbPbJ{uOsqhm6cn-K-d678}o)jIm6bw<Y1mavhAf`!(mewmZ*9s#I-atTD!`)!8|1nL*&;Po?qiy{$0?'
    '>JMfGwute{n=fb*4hs<C52e$9&B^z0VYH_w*Yd_lz3vNI=F2=}33gw)m-+k3$UHqen&S!EZ}?@y%<`ZmsF?Q&V>!AC+4m*lOlKy`'
    '%<%jA=^`G!1oty1B4G<>0A1SYaxw=l>X#)EmSDb@ITHyrWkmF!kSu2lbj&%;o4|zNB{<`f$P2jSB^9>w++`V5q0Gd{3@c#Fh!}*!'
    'MxIrObA4k40+`D&&n~l`egX|YJGBVj&)YAk0~JG<g_*gsVJ^n9UK-=Q+Yf#A9Svb-W9B{f%zQf0L^!ZT;PBt8u!AN=A_;Rf_oXg&'
    '&Tb6YFl)wxL7+cxr{Gcg9SLD3Bj(-5TA4y}CLu-3$yE<C#oXK?CgImT`{o&m#q_U^Ikm_^tCZ!4<t^d~3}1o`4p|Tl1G7aAnp_+?'
    'YndA}CS0EPCG(yEYi7Khsw6X%aT|8PE`uCj?7XdI1CT|UU-n{_Ia_9y^)Iqg<?04qzA_97duD3G%;&XpS{XwP?KQ_8d*<0N6m5r?'
    'jj3yyBV4=|%(~2lB{P|0PC{J--T29#Ihj?^#DY0%nQ;~EHqeF{%`+z!%rc*|c8|qmUUsKIGN+@o8_Jn=foq?987KNk?BrO@jsk=*'
    '*HKxAXZ~`Ixk#6p^CFq-n4z)(>~huT)O@;}N?M2NkJI1+#?M{MMF{gaG@Q>YjMFCgBuWUxJH`CSy=v=dZb#bSJvG%Ei*jZBPRaAV'
    '5azL{rNmTWBZ{gk#Hc{T(l}ZEN;Y3iAaTk|GBLa4q@y<$nMCt@e;Mg!-i_J9=6YoEKgWrHC@QB)7T+y+OLFj=*?04+>tTLtzDsIc'
    'E_3fb2LwlACJxZ4F(Hw``YP$4=HLE(6(?xXi5c<S=y}MA(Lk(XF;n1D=EQK!kiKd}kjbB$$6<c)!HGFHFmv3-KF)sNWh`cP>B5}8'
    'HpVkGz9t5iv)O{iW49`Ne`5IJA5}#C>deHAIe9<-QEzM7Y~EWCEkqO)PR!`NDZ#BR0lhYJ>B{``{AWFHnM+~S<ssx`#bPm+YKHG}'
    'u<k^2zysP#RFhg!AL=NoUvsB7yZe<G6tS4)_&`3D8#Hs-2i3+}xR@KTjL2Nki{^Olun+#U#}l=*bw_3XSY6mR)Trt*EDR2XvFtBY'
    '{u4OYRhwUi_pnvppuv~JRJMu>GXUR4WUjt4yBx9|Kc8|Q6b{U#b2}D~3NQ1_(jkWWBAWK<8G@+H%!c{pQ1YYgq99yMYk97SIL|Cy'
    'I6&+$qYfi+xjRNQp5EX~)pwQNc#(Ceh^Ji*K!>|F#Nsj2r9z2{nPz>tLaHJlbC-}4#N#o;%C6xN?E{J-P&s_Li+V=lG#0a1v;%M}'
    '&7HftkD}mK`8&OOM%AaWm>J|YE=rl>geDdAgqwO!+=?4Qb4q|w<FryM>T+@;W;DIzU-t1QZhh-eRXH>&+IJePWmgF{>1M$tje<=I'
    'PX#es={XKAPjOd_ZIqm4&0OdGIhMaqs>-*ARrjJ#aYe=@71PQgYhPT9f;hwHncKAdV@+u-I<6YshUj4X04nI%_9_DN{Zy^SavY-L'
    '!YrcM{2y&(gEeg-mATwx-8R!eZ8w#FX_)Ut+XsoAJl}?0AVO2!xUH!U{@Ol(3i7i9G54}@yIw;``F?Bbq511O_Hmcc&D=0C3mbW+'
    'b(mA8EROmx*oq0SGY70=MNeZff3Rv5O4@*amgp5jg%k6`X!A@gn2WaLMB8|?Oh?b?9NROOAd;>tfF*O@#`%<hkBm8zS=3We`V>ZE'
    'CN|8pWzOm%(lX|CQdDv27R8ephA|VxT)eE_($8n23g^80-NS@ctaG<jA7>T8fatHP_j*s{MI)&k!f>yLxvp6Uw7$2C%mOj&$(;LH'
    '&#ggGDrUJW=pi!}2NjNJ5}EnGtUARE%rYSXkL{~Pe>zD>QUNb{&V8FJ<sI{R!;G087`qtsBljZZ@^RH0bL;yfvtm}tMWza8lK^CB'
    'v74wsbtF97xH~iBk<g<$Puh*SYQDQrWn+MUhw;%g6gF?{>)F?NKzgU-WqEGu;CET2Ai{yLys~+t7?=}nyS7+^GQ2!%&#qZ4X6nFP'
    'Cov_Qq;AX)z-h~j8Hi(W5F6$~b*tx16|_VvOR-$hgtpmFmsKR@lGrwodzgMz`}L6SzopQ|A==a-{IxSP^quGQX;TYWT9n_^?PZa^'
    '>=?9hJU9OB+`S>8ckesYRo!4s7D+3@wk1s4U8`#QN)`uWu8*F0I2}A_Do?y{%4f?xnRD+RgI$fwV(1`hTXt2wt!9QE%-FjDWw+TC'
    'exYEb?Suh68f<3X%zW@A^$pi9ol;71>x?WwoXy)pp1azBU5R(Ob!Ly9V)$`eEwcb|HbMt2$@)$#Acs!Oa!<+K8ljq)ONZTv4UN|G'
    '$4+?%ZJVbO#9=NRm`Bs}C3KSKN6o`xJ`H01mSD0^^pTU^cnFe@Df4O`?5Cd7aAx`CKfNsgh%?bHzm@sLHa3qEKX+e&GtAs&0}Ww*'
    'h~E(4)uq`nY-3^&a=$RaqA5o3@P!ZZ{)UDQ`bPLOqpnd(ghfc4_D??aO3mEr6d>QW*qK+CPdqvIGau%<pEdAnhwalw4o`~zJ2P`I'
    '=}a5O%-xxlddwUX9UlSzzP9ddKCvEdrrv}rxB4dD%pZK1^C`1bxaUrp6hPH1_hR1Z%2GHom#U<0>6920!i;$4!900G6PZ*p*Ll9Y'
    'KIY2d?CRDAeD=^E&ip2%ScnhvPG_VdN?Pig%s}Yr+!2_6bgAX!H6A6}96!v1nSaP#3ifyzqXY93$$ZDkA#BE3ojH9n>L|eM9Pj4C'
    's+FD&l8xlWsHwKpm?;lU|6QMX=m1-&jnUivRO!*h>oLPZcM&AQ*Uk6#JM}r~+Ij<WU1i!Z<Jo3!wrvqYnXzU!r^46E_x`z(vDKOX'
    'lxLa^YQa47?0<gRSAchDZtQg+EE8?dPD<}9=VaQ+wek*lT6oYUa%IMIfh66+z$-JON@qsZVm8qXQrCIVCODo3F@vs0V9%Tuo&{21'
    'ACI(HxQv7`{~gtsVU>R4X>EWWh_B3?s&Ke&cB`|yo;!E<0A$yg&)3`r>zI)VGq~d!Qr{VL{|vzEm6;2ysmy$-98I!h9Q_u+S8Hx5'
    'wZWm!GxoNSI^*cKU8{)on0cx(UwAVYeS<}nE;fH0JPl<=n##O@#FLrz%xPT{x|rWu_^m)@)dq|XW#T-U)dQ<HLTdIovMiJt=*&x*'
    'lbN9fgJNzE!t>i<fdd6PZ}sXh&(v${uKEIC9~YTvD0AA*oHcVk?`Y9&&3QZ8+l|}nTQcb*=gT}Q94L&;WjJ$t7#da{@pNv8(a$MN'
    'uM|K8Z-mIjY=MTI0_(zoXHO|2cq1G$FP>pdjhix^Ih(bfc_=d(ch_CC#|=B&2$Guw8U!;d!6V(1|JIv%95p(5=}Y|p`(-$DJ}|#q'
    'l57Jroo62T)djU@E^L@lu_PP@??sX7mRmY*@H>bNvA;^WG&57R!7Np-O^tOK^fo{JAOGh{Kfl^CBVyc+X;*!6!2@l_EOgmm!0(I#'
    'sgb$pIx;MT*k`8No;ve5qOCuiySb3=EiyMM3Yi5uGxpZfom&;2G7D5V8WtvbW?e)D^kyD4w{6KDWWBb|yO+2zBjY?b%xzo+_tYCZ'
    '%wUJPSh5<Y!#K}PrgPDLk*9uUJ8d7b{ukgbZr+i(FwJvQqoH{PF1<6^r^+Gge?ivyYuwi0{F24(N>AG9src;&p3M2g8IbkApzCAl'
    '7`iy0OPy)VZK8}9Gv3Qw4sQdQqj|&^a*_HrZ>hl%Z)DE)GV@VyWbEjAW=37m=bFv*sI#fsk?oad*6%Ow%vZ*<2N_z^B?fh8WKQ?a'
    'GadEK#)0l~-GHul-bRdxEDc>=cvTEYCwC9o;BD5J?}0c5blpCibj~m_TVmT-IcM5}EFA=;I~Fv5xKF~F$F1;?EXDKwG^0M%B+x$Q'
    'a^zy5t#>hogrKn)R`of;Yo7b;Fgj)yBj&=T8o$-OPT7@kzw`@)pkSv-W`D!0dAai#D>1XS$C2^cFV~rqfm6Fph{Bw%$V{}FN~&Q+'
    '1ZHS`XMl{?*e%)l9_BncbNi8HSS6@R<))WlAM^Xs6Nn-k0NIAUp=#0KpxTSO!UR7K(g))(!?tQ&6lMbUv=ywL3|bIYAj-f}PYDa@'
    'K-Hp=q%$j3k)c7^!7>i>=}_&#Tb`9SmuOE<iNWa#%t}WWK|x>5XOz0c5luC*xXej7Gr^OLfc?xM8Z)wr6v`H3>*xWQq18O+<}NW4'
    'C7(~3IS5HV*l+oV&2xQj;1<mHFJm$1!SY;3Qx_921ko<Ml#$0{DvmH_8Th7GXqaQJVhS`3(a&`odjX8h?LVL8(F7U?GryiZD6DmF'
    '@0lO`1Bj^YXjmZeTd^Z<{U_pQJ@fs)ipDIbB21pE_k4$$>|=H<uWb~LB1|@>x^jm3Hi)J;x~fH{d%46Z@gyBtT{-FX#-~xdG96GW'
    'eT)P!-<@L~nwy-0`>~nf8{(OOFlA0g%y?)b1DC_g927^xoP19`6FrK_T^$-R-yb!;;qjPZ>#<88b5A2l^ljgFnJ+-vmsR3<L}f=B'
    'A$%%4jU+KifgaZ#z6VmJtv><$Lp<i@Gqd)L^}xsAkn3!oxs&cs;71;Do@wXunN1ltD~@R+?h*6DzIgd9P<<A0o{Nt8iFn}I+KSCE'
    'Kj>xsHh6YBGIL(lsV0I)VIDr^Zl8g67hIf2lnvG}XNE)p=)|0JGGbP_0(Zdu(|F8(CZxYSub!EXhE9nbIiq7{s+s^l{3IT;yqKut'
    'bf25Mq`NS`V`JGM%AC2Ekch(Zw_U=@EHidt#vk}#Z>SwxM(mtNWv;4M3(3KmOTr9(!AJYmr>fz({16(G`RP*RkP~zESd5s@x_aQJ'
    'I4U!$7CXB;B+R5k)zkjRNb-w3BJ(dww3HR)#QX^=hm51~)I?+kkKj_4U+R)Db8-mg94?hSNt}{=P&EWv4}beHD)TL{l=_045@v>b'
    'h;ed*2uvZ=#~D~|?e583jN%icGLQE;uZ?h`)(4+{f9R4M;$uOhGUG61H(dqg4*kPAD`qWb8kM=PU0!?4mkZo_G8gB@%W-U#2mL@l'
    '1gT$9f|ZzOqytT&yv)p319LIR$ZfFF8l003^>b3kJm|i%Cw1;Y;=;`5!<T>?bJCx)l8S@a11}b<QE|M9OYXKzd{HOZbY<phMsbkZ'
    'mP}mopk;zS7V7iqy3G3*p=bh=QHAZ9k^G&)E^TKOW|jH|MQ)!5EyLGw7v*29%WVAk%giCCSY~Gm;L$n^IM+KYTrXwCyz2z343HA6'
    'JI~DZa%Dcqnx`rias}qxo*6kXr=rdCODnN5Gj~mZoDZ@tTjp#H<|>G}n3tobh6=1!kPYO(j2udsAQ}19xBH7ck}zh|{ZhwF)@2rs'
    '%!cP)mC|E(l6GDEZVody=}=j!J?WTHOy<;~^ovtTRa`wIeFW*5W3t$q%+$1LzEbA|dJaBIinX?GXJ%sh;2*k{diTMXF`1!DxtheK'
    'x=oW^)b{w6aUv@+mu}3$$jpHX&a7?{GdI3i49pa*$1L2Knfb*kg$|MvQyO$|`Fr6MoKzS;xoqDd>S!bcj)58W%&29)T8){wFdI*&'
    'ZC+*Fla-v-<tU=L45lLbQMjC~j6#~19rG*sp)_6qX6mAHGpFKXU3X!gy!}J#C0UKRaCq^;L9=Bp+63n{nYsOo%jJl}mYKG}PYGR#'
    'S=bBzQh5f&oT{WhvRFsam$|fOW|qt<b(2Pl-QG2O#HF=jEEcAt)R<G*a4HJ(iA#w*=v0HV3B;_K)#}4kNz<Lkwy0U{Ix#1TnP%U~'
    '50tSjFS^1rYcLm<L5*Z-izVO}b$y@jsH}%f^PkjPLIY5cQ%zp%!VH@iJZ_l5hgw9`bU+$=4Vu(l=2U~T{ZW`El9_=oh6KqXwyra+'
    '!qkbmRTK9JdR55m=JVUV+&zeTgk6A1oN92kR?#^@FPn+Ijg{P?Z`NR@QJA}`FX$!HQq~cV=rLbZ9LT9JPtq~J`ex8k@`s||uQAUo'
    '3Ue1TgT8&BH3DCU*)DjLE$aR*%ICpo2?O{wxs0zjW^vq@LC@Sik*ntI;8)KAcW*al;8vzQ??QXpdHte!JC$u$@7`QytZz;&GnapR'
    'Zw-023esI<o+KQ%H5p17$$hcLJae0QW)?kK&$TP)ymcLbEWW*AInUf8XXj#vxhYfiyXdy4WiYg`ZdMLd(KOsO_WLs4_243o8*@Fc'
    '#h&VD0DKnj8g>yUbL**>PlUc_{)FCG=42;*rTgeF;~Pml4l}sY%mCP=Dg!Xd;ESZ7xs7VH>k-KyxIFKfWu<G<#sgmuGq*Z#mgzgj'
    'U>kqJ>Z;KVGrALfQ(>{@S>`)tA7uH|u2PavA(`;AgE43B%$J#*<Sy4E>nh_1X*;(D*_lUAhI^x?rE<Qr=BJ)~dZU?TOu=w3ajDuS'
    'p?{C<l$kxmrasIW9oOJY8pVPBJ32G5l78Dqsg<B@vq9h=qZ>(fl4M=>J)zTN=b-3f=;TOBy!t6!ooJ%MK&Ye9$zg{=dq7=w?m85k'
    'nXktDg>63(XTy%I!F&Zwg<6A|ixrq#9nIp$xUR_DItbQdrfV?Y|K$~kbWxv$F<W<RKdbL$BQd8g7gx!S2wgbL4GVTX8<;I$?8J=g'
    '*F&+=O{{@A+hNWe^iu&)xfXM2xnP}`8~KmKj9hwG?=oXzKhJA2b9-iJ%iPv#ybk7kXPzyiU+$vzD&>fnPejLj308=5H8SsP@z9PL'
    'N&iuE%~pMJ&CE@s4Pv(mJZY~p$0p-tOat0so)cSUb)7lZNq1u!Ne;}JouQPettu9C=FLp4Ga9inV>IS_F*ibPDf{-!xq7`;bn<r0'
    'MQF=h&zoJgc~>f2V?MKL%xAd>?U{4CEFYM6El$VGp9U~v&m(Nv%%9CS{9@?#AhdkyTBVRE7PKX^ux9>??!joxCw5(R?RIZVW@gR&'
    '=c5*H_I<dV1lp3hsNZRI@c5fiA!CQeaxMaG$*eAQ9DFDu+hIPrio<N@-VpB0d(Ov6u`)B9YQ*bfPHo*Aa4JET%vF45WF2q2WAR%t'
    'LjyAeYco#^jM!dmS_j6i%nbaPDOe?mkl3u&vi%L*)pBHqX3i!~5Ibg%8|QVHdCSaPPZi~%6HK$oGqz$*T%yzCCu^pYjVHG$Vv_A&'
    ';q;oAtqQNqSTp=U38sk$^PFYyASN@nVpeSisq@7c3qN){F(Y?oICt924$sWnX(!IEh)(oUau{al&YaFM`&x9a%s~HY8|LS8%#cN7'
    'F02+*IjP5Q?eXcoI6NXViOIajCI7o{U+&K5uFV`I$A@5s2Vo|_fw}ZxX3?32<)$X=3XmOynF0HGwqSO;7V~8;;?A?vHLoXg2^^T='
    '^7kW`>vT_MZp+N=m=l-q5Km@iU8#1`tHB|*lSU4QpiWhcZw525WG*ecFT-k`O(n69TgAHEXI}BB?3$PhU>99`x<2!AF0teDMb$c+'
    'iVrgj2+@knEdCENr#FQ;U6C2B&s^HRv<Qg3KQMFRyf0k8Y(!xehh;|2Hp5EHnf=GX7|dl{W^Ri>1M&sRxZ&~K7J&rB-bZFGY+rkW'
    'n5pe+L-GYgTxMd4P=>_bUlTLGLCm%YEJQZ=fteH6Bi-uEWqjsz9p>DD8Mz+!S7#Qswj~Y8C5g+-ZJEi<VP>{APf(5ni`y>Bl36%2'
    'mvAj+YRSx<FU82{X%;b=OIv%GxiXhyMSVTYg(Gu$HWq9elUdkK8+DXtt}S&MQ*Q{{c_xm`L_1}H>tGhZhZ)DbPsv@BeeS5N2IlNz'
    'L}n+&nL7$(+Dn5hEEDgp%}EKl3S`>PZ2E2uW@<Ih1h_GmDg`Bd8PD8MJ5_0?4zkkqBCmTx`ecXsEHvaKv7&J;N)D?(bo5VmR?WT8'
    'E6vAN56!vQN8g_rrumflb|`ZUGhp8?+yBU0`Sg2kg<efCu<|(1rz_pN`hBwQJntx|5huF&%*hUO5$G~sT{hIpA>-0Xfy`ocX1HS%'
    'vOs2j4b1-t!rc6aV%}2**xM9k*T9VbA2P46>%fl5k3Ea^ACNhpswZ59G1K*#arIj4G~fwfF4sqvo60jDg&7}e3D)10u!zhDK?Wz2'
    '-5PraHD-sB44^lx59#2XMRV?WC~Owut~)N~{GhTiZ9jc{%<1vX^SN(pvFecWe5w8EP7w2<=J}p>Z2gc?e`Y2Q#H??8KL;@%Oi}2C'
    '<ew9NL;PUOsm}aWz~O;k3p4Ufp=g=OftVA`_2sLr;Ex9~_(!F|yFd79EA-=m4pzI&sjs#|uMW8lqAG&50nqD1u0i;5tgOA&)#r!Q'
    'by}5Qe~C;F$vpNdBLA;FEVH&J`ikU9c0jeE8^I#Tk$o-9)$uVye{F>hxee;u3lF-Oxen&kf8{6Fr#6C^i|b)7j*c0JZG-fBm`O;a'
    '8oeIJSI~XIwa5l|7<8G$!Eudi+fzcb+K!Ali&!ObV_tCcA0e|iGQE*UvXRaY%p7A+xi~^*TpX5}9vO2i8wu0HGLz`HJF7Ea)8$|g'
    '^RcPtwprH3d<a{Vg?6~ShIwv|DPJGg8su&B_@kTWtU4~)sCC_~%Og7v9@!GCeFgt^Y`X3=|M}?lZuI=;>e!e;_5Rq7u+r#1LT3E@'
    '*xX2i!Et0x#`5?U;So-BeqB!UAdBPu(J_PUhoeJQ-QKpbjcsgW8{62%Hny>iZERy3+t|i7wy}+EY-1bS*v2-tv5jqPV;kGp#x}OG'
    'jcsgW8{62%Hny>iZERy3+t|i7wy}+EY-1bS*v2-tv5jqPV;kGp#x}OGjcsgW8{62%Hny>iZERy3+t|i7wy}+EY-1bS*v2-tv5jqP'
    'V;kGp#x_Rde*s>?+<E'
)

BORDER_MASK_B85 = (
    'c-rk<%Z?nk6(!l6ZpvwC%7$PJqOnW^S!iJxvj_q$6qynPL`wnL8c1iCU1nh*Mqn6}Z8%;T`h@ueFSAQ2$p`2If<&L7oxBK;^t-F3'
    '>%pqxv-=!lW@Kr)ibdYXxeu}k0RR9100000000000Mdk5e!rE}nC0rn{YZy5TmSrG`!_V-{_%C>b9=vHpj5{<PWtlu<aF)L-rw9T'
    'iNh$mc`n<9>4W*VZ#3CS^OqIR6qlIjin(Qk{_o4wgy(Gj#UmQegK_cybd?7g^}qUEN2*Y`?6h9pdU+P+WWZ|U?Us0y*ZtnOSq)xi'
    'vuaQ3NTlv;=k{E->gE<7{`kk%E04;nXcLqCbYD!$sGP2nAl0o<=2jierSD?R`Pz`X66pf>oaF6#x^hF*!yLBrWOCZ+Ll^F3wE^dw'
    'Td$d@>clKY^lfhDT7}I)KipX5?Krw9QfA7_sV!ddUBMox^)%Dm{$f6~EB50B`B{u#Z5%@v12f5uy_UTJUspjzB8NEJ`hh>K<hhg7'
    'W#-h0k*}<V)Fb`bVyF)n*5a~-QtSzbp*b*@xJG<jK{#n4_%;zzYEDs4|7yWzEW~*eFMUuDYT7A?8vW=|mWzBx%vX7`_``3EKT=HB'
    'nBDHKEm@Yt37w*D?2ldu!qQAkDBl>lannHVcMBc&@Ut%ZT}KiBQ<Ux9wCi3$$~EF7E3;~|fkVDrPU$a;vij$ucj=7^OY&WnFwHt='
    'dH%Khm@Yckw}qf(pr#b%XjE&PC!J|*wjA10jz3?F|FSs4XT3SYctdboa+89Ph!Vo|r&fL3;)|ZHWjBS|X2es0X<I;SqTrv_@gh3F'
    'X6LnjC*MzPs-9ewYJGZrpsJ@lvxW&Q|H~&u)?jQzi_d+F{C9L|MKGj8;$OJ7*bk`oh4O*nRdww+&#Wo>$@AraKP1zW*OqO_p4a%G'
    'Xi}u=V=k6fdj8*>eDH--+b|s5*s$oV`-SiA2mNQxM=S=Fz?MdX@wo)brPxUu(vYn$!+xss*KdXpgg4~Z^8~@Gx%%ZM7TJCd`EQ*+'
    'adZClgqCf{o!MYMKs$J!(VKpzuA~Q-^&ENJ-MI4h@qaknPOn`}W!TkOHsq{1Gcv?)2{#p*h20cQ6UD1&+0-mxV<j=XYo+?c+8j0i'
    ';N@k-a?(=#xL3{D`KU)PtFC%`C>>=+Hi*|U22~Lb&PeCvToukIv&!JSN&buUMxDN`3??Nxsbk-Jx_w$LCA>cAFm|C3qh))>m4Vr)'
    '$47>iXJUtE(K;nM@8UtLQ!;nHC2mu5AFUFClP7|g<X!i!!LQiP%*rr7tuHSw6(AE?`I%Nm<UP_cpS8NmsI20@8{9WiW>qWgqiV)>'
    'mf&Ko$fJLktwY{W&@9`d>97Epexon%meXspWB~PkW?@sjD-Y}M?FoSG;C|YFl+NX1RkWzZq0rr>F8;B7rmfpzedEt;aE>TjOf6IG'
    '&T7Jbm<NP6%Qv3&pqOl@8!}r>Q^y#B>)q4xhWk8RagD3pJui1cRf@$$ThU&v49{$pFFzY-m(7i#B%{YAKHB1WSoxvmn#k6w(Ldso'
    'jeQ{NTZ-~ZsHz**1QcR#f-d@1Tg++tIejy~6a9<51v?#1>}i*$67^J>_ac63fN)S7jMJcR#ulM_-N&%+O_3ztk#(83A>;d@SDC9y'
    'v8UWt#}}(JLHuHGW`^~}<c1$V%UTrmo~T<tI`=1!xV?r;F}NhW5tpx<9(c?xZYfa2PMA|ObJNxJ=~d>Ud#9`M$c*+LD7z^g`t>4-'
    'VLZ>%+8T31vW61N=-3*$c{;&m#h`9gswQ9S%ljk@Hd;h!7tgnT(hF^|1%Jhlhtrdcco2@W^#y-*y90S(=1-&wi!%-8yt8?eq-v6!'
    '+1@h<60Vn!E()ldhB;wkIJq<Wv}^^H9jGO3s3Xkw7f%zX-PmpTcG-H;fS>P+Gb1F1&5efZ%^fzoT#-RxByA=$GT<C<hW6PqKRVly'
    'A|4>R>M|E>KJt%LWqPA_Erh+S{=%7F_R`gPf5FSptKF6C(}EdRRyrSCMg6Xrr5RrDF?H=o{B05=UA<;gAE6}a7Zx#IEgAv0MYRiZ'
    'R;NDy43y0>jF1XEU@A81Mcwp%-?u}DR92a;$XsmKc|e>c2$ua;zt`4H-Yq+ZnaPSF$fZwqpon9wEy(j9D&_7QgT?P7@wvNxJas`V'
    '=M}C7U*s!t`l>E+;4XIYGE0=`v`)nHE~7Pbe?quO5%l%aMvOyCf3(V05AyrNX{c;DjfA`6o66l)-m}lT9}k>?mXA`ZSu+p%Jm3ix'
    'vQEW>Q`cbY=#TP~Nc(|^cA5{Ecg|~)7Fg#ID-t>}aAu-Bs%s?Z^pGd&$k|AT*;-ysXVC_gQe87Bu0rz*;V<H_q%!on?Ue?8;=ZB8'
    'IXa4uvu>N+Iw;3YXGiS_+b5Wbjr?m@Rr!f4v;2$?G#tv@0<obUms&A)%DNrr?r*6)c-!4j_4fD~-)Vin9YfVoF!5GJR3trI*lid&'
    'C$0-OJeiu7>!S+eS3ftSp-oXBk8?IpNJB#eXEskH93-lSjv|juK8%Q!$i15anxYP#4~kD+oXY2#C1rtokE#Qa`5{0|Hy>dY8F+KT'
    'Q3m2jtesLkiOqZSz{xsdxs8SiU-hVt>!n)$O|%^q=D!$|#n+V7zAD;QX)~4>HcAFWxQI1|a-<j+f%iz%OWBiySOC&;ykl}$8KQSd'
    '_?B}LUyaThrhRs#S+&pfG3og(o`CqRPS6Q4i)Vh2nDSe4{{u9jLaAOV=(qTM?OLo;0|zH=j!5b>WSxbav7RnXcO9ti<xQAHn_+aV'
    'Us$-+3(t&SSA8lAG|_pB!_9j33xy-JqWDu?Cq{8bWh+ePxzRx!POA`)m{l%tZoY-CD|O{|C<#q9vZtQ5<S<K`xVCMarxyxlGzG&^'
    '4gz)H3<5Kz8nW;a(PO*LnfHTHvhCR$OGTWLB$|DzA}XPxEFBi@+PpDI^X?{x2TtAS7ionDlyuLsu(11Fd2vHfD)zb0eDPa>_B;eh'
    'U|PJO>O>f4B*BiVF#!xYDm}7UQBjyhncTdcbPY3knA%IWx_8!Rjc<eusIrXplM}g`>vud3_UYo=<@S{8@)5z)ThVHO*vbg)oG+P>'
    '*m{{lkR8?IrhShi@yepd17}4=;YISUq0K1wT_YN_S2BgRnh0@DdY<G<1DqNmd)HxUm)AQ-1Hp7kf~*3#Gnt^~>Va{FT%{#>^xY_X'
    'S~v=$M<b617&Zu|>U7J+@}7jz|Nc3Eyg&EO0xXiFBiMcAa*ucKqA#<>*1CKzAsR`STFYoseDrMnu1}$34h0V&L&}e1t2K)(BP)EL'
    '4aSCRhF9@^l8TSX3R5go@r*2$Lm}#CJPF}=H|XK%L87DzgDKL<wIxYwgUN^pf39Tv7-@tY0x;kit`4Vn%YmqOM>!s@dd~>j7*Gg`'
    '1Ja5IbgYHkiTl3atNsQYIJ5IWJTmP)38qPG=M|*P@n~Y!uF)|H%PJ$7dw(Po<O%jw@M9M;C(9e|HAyR(K9ZIdhJ&_N**$6RvE}A^'
    'Dme{wA|AW;DmtD<>$rqpV!`Y!QQ^Ji+A&={m~*iV9!U61l`4P6(^cOTXWX566KO?6$<qDo*ylz$Q$9&N6mPPja-aDk8(ti(z05?G'
    'V8VtUZ#GvR!ahq8zeUcx27h)v_q~MjB*L#mbBn(yOTSDLj0bp?SljU|>UnyW=^a8qo{6`zQ|3dReXFH3Kbk6?dfcJ5aMLWoUNxRl'
    '8%KmpT_<@4&e7*DqH2dg(<5jONxsuXMmgxr%!N?<EBWFvab>&RneV5p_X17L7Az`bmp5B)9if^`jSLWV!<9I5NuiXhJ!39cQJ|UI'
    'GOLsx-l^lB>7~UC=tcuY)GbN!FoGBseXBGxI4;bdv9N6HuH2~!OFDkw$+Y{^Lrf7;3%Vi^B}3Hw<6{ds&~Fnwl0{aEiwsinnGL$C'
    'NFvvili<zvBDt*kOvwRr62ha*^9XcEdw>j3g`yYfX6v8HD7z1{Bj1FLG92+!hGVh3Jmrvk@FVV{)rUs^b(G@AjbCA_VV0a12W&UP'
    'N)ItO)i?+YyS7R~%u?Q}F*|{^@+b6H?$*&o;{1#G*VvgzGkc~$(=>?<-<b?a5^xhL{kWLL(Q3&JnG9Wj%d!M1hcnah%Hb2_iIs6w'
    'a*+W`C&6~x*BFI$E<jUGV$wu>2^XnVyhT|eQa<aN#F<7E*Gw~Wn%)p@6i*%KK|!%)PL{%<rA%&SBz6T^mn)j&p|zso`18m~sdSOX'
    'g+36R+a5{-rzEvf>+?NE^SuSmA>F$A#r^|Q=w@Ox5x#n3W1i?%sCmpJY5fKbk<_-MXCxn$xSUMj#QKF?XnpN=v5WP%N_^i5(;IR`'
    '{n^wrNfO7CAf*TLrW{2O=R3g_xHts3&Un0+-k5W=X{S~oL9yVl8kIGs+Jg!zbjkQN?JuC}u<k&x<&{yGA%2`q#(s$*Jr@4XQc>P<'
    'To1v9{!$kCwlyXL^Js<u7Dzl!)QP9<bfUgVANH%@6T>V$`zQ`)ud;-*^upC+j>~jhnq^|x53B1?MVo-j4rw1UOQ?=cQ<O7>1Ef;z'
    ';ZUg7fH@uvk~y#Durv3nWU=V+ure7mVroBkl*K3aIz0!>j`p330C*%=9RL6Td<Fmj04xzXytFBDmc&a1hsTn}>K=m8JUs=tOs{Pr'
    '!E_S6onA(1IbKcD?V<`Z_(QM9akK^!Y>2P7bSm`n(5T2Yb<6r)Xrn^y<1lE5z=n8&4V%Xtv}0`nz%`y@3fzP^qty5cw;XpQXev*G'
    'kRmlCipF+akV$O(44W)~4w_Ev(=<XAdtvL1KykN*ne<{P#srBo$OV8cOI^}miX^wu9s59HC(i-ZZ$toO&;d{mAjW22mE2^FkIO)h'
    '!L9%RK-20$^DI;ffJ4GL)CVCfaBQFo;R?Z<zAC9GJ%fI@p5)}zk7<rGjX{veA#JXcAa-agfD!`TAX99U(O5SC000000000000000'
    '0000000000000000000000000000000000000000000000000000000000000000000000006Gx|3wW+Km'
)


# Codes used by Proton's API that differ from Natural Earth's ISO codes.
PROTON_TO_ISO = {"UK": "GB"}


# ===========================================================================
# Design tokens
# ===========================================================================

APP_TITLE = "PROTON ORBIT"
APP_VERSION = "1.0.0"
PROGRAM = "protonvpn"
CLI_BIN = os.environ.get("PROTONVPN_BIN") or shutil.which(PROGRAM)

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
ORBIT_CONFIG_DIR = CONFIG_HOME / "protonvpn-tui"
ORBIT_CACHE_DIR = CACHE_HOME / "protonvpn-tui"
ORBIT_CONFIG_FILE = ORBIT_CONFIG_DIR / "config.json"
ORBIT_INDEX_CACHE = ORBIT_CACHE_DIR / "server_index.json"
PROTON_SERVERLIST = CACHE_HOME / "Proton" / "VPN" / "serverlist.json"

COL = {
    "bg": "#060811",
    "bg_alt": "#080b16",
    "surface": "#0a0e1b",
    "surface_2": "#0f1425",
    "surface_3": "#141a30",
    "border": "#222a49",
    "border_hot": "#3b4475",
    "text": "#e9e9ff",
    "text_dim": "#8b93b8",
    "muted": "#5c6488",
    "faint": "#363c5e",
    "purple": "#8b5cf6",
    "purple_hi": "#a78bfa",
    "purple_deep": "#6d4aff",
    "violet": "#c4b5fd",
    "cyan": "#22d3ee",
    "cyan_dim": "#0e7490",
    "green": "#34d399",
    "green_hi": "#6ee7b7",
    "amber": "#fbbf24",
    "red": "#fb7185",
    "red_dim": "#7f1d35",
    "land": "#132b3d",
    "land_hi": "#1b4052",
    "border_land": "#1c3547",
    "excluded": "#7e3048",
    "preview": "#4c4a7a",
    "route_a": "#22d3ee",
    "route_b": "#a78bfa",
}

CSS = """
Screen {
    background: #060811;
    color: #e9e9ff;
    scrollbar-color: #2a3155;
    scrollbar-background: #090c17;
    scrollbar-color-hover: #4d5a95;
    scrollbar-color-active: #6d4aff;
}

#main {
    width: 100%;
    height: 100%;
}

#header {
    height: 3;
    padding: 1 2 0 2;
    background: #090c17;
    border-bottom: solid #1f2542;
    layout: horizontal;
    align: left middle;
    dock: top;
}
#logo {
    width: auto;
    color: #f4f1ff;
    text-style: bold;
}
#tagline {
    width: auto;
    color: #4f577d;
    margin-left: 2;
    text-style: dim;
}
#header-spacer {
    width: 1fr;
}
#status-pill {
    width: auto;
    padding: 0 1;
    color: #6f7798;
    background: #11162a;
    text-style: bold;
}
#status-pill.connected {
    color: #6ee7b7;
    background: #0d2a24;
}
#status-pill.disconnected {
    color: #8b93b8;
    background: #151a2e;
}
#status-pill.busy {
    color: #fbbf24;
    background: #2b2411;
}
#account-label {
    width: auto;
    margin-left: 2;
    color: #6f779e;
}
#account-label:hover {
    color: #c4b5fd;
}
#body {
    height: 1fr;
    padding: 1 2;
    layout: horizontal;
}
#left {
    width: 1fr;
    height: 1fr;
    layout: vertical;
}
#map-panel {
    height: 1fr;
    background: #080b16;
    border: round #232b4a;
    layout: vertical;
}
#map-panel:focus-within {
    border: round #3b4475;
}
#map-head {
    height: 2;
    padding: 0 1;
    layout: horizontal;
    align: left middle;
}
#map-title {
    width: auto;
    color: #a78bfa;
    text-style: bold;
}
#map-meta {
    width: 1fr;
    height: 1;
    margin-left: 1;
    color: #59618a;
    content-align: right middle;
    text-align: right;
    text-overflow: ellipsis;
}
#zoom-box {
    width: auto;
    height: 1;
    layout: horizontal;
    align: right middle;
}
Button.mapctl {
    min-width: 0;
    width: auto;
    height: 1;
    padding: 0 1;
    margin-left: 1;
    border: none;
    background: #0f1425;
    color: #7780a8;
    text-style: bold;
}
Button.mapctl:hover {
    background: #242c52;
    color: #e9e9ff;
}
#map {
    width: 1fr;
    height: 1fr;
}
#map-legend {
    height: 1;
    padding: 0 1;
    color: #4f577d;
    background: #070a13;
    dock: bottom;
}
#actions {
    height: 3;
    margin-top: 1;
    padding: 0 1;
    background: #090c17;
    border: none;
    layout: horizontal;
    align: left middle;
}
.pill {
    width: auto;
    height: 1;
    padding: 0 1;
    margin-right: 1;
    color: #697199;
    background: #101527;
    text-style: bold;
}
.pill:hover {
    color: #d7d2ff;
    background: #1a2140;
}
.pill.on {
    color: #e8e3ff;
    background: #2d2266;
}
.pill.on:hover {
    background: #3a2c82;
}
#actions-spacer {
    width: 1fr;
}
#quick {
    min-width: 0;
    width: auto;
    height: 1;
    padding: 0 1;
    margin-right: 1;
    border: none;
    background: #101527;
    color: #a9b1d6;
    text-style: bold;
}
#quick:hover {
    background: #1c2342;
    color: #ffffff;
}
#primary {
    width: 17;
    height: 3;
    min-width: 12;
    background: #6d4aff;
    color: #ffffff;
    text-style: bold;
    content-align: center middle;
}
#primary:hover {
    background: #7c5cff;
}
#primary.danger {
    background: #7f1d35;
    color: #ffe4e9;
}
#primary.danger:hover {
    background: #a12543;
}
#primary.busy {
    background: #2b2411;
    color: #fbbf24;
}
#side {
    width: 43;
    height: 1fr;
    margin-left: 1;
    padding: 1 2;
    background: #090c17;
    border: round #232b4a;
    layout: vertical;
}
#side-scroll {
    height: 1fr;
    scrollbar-size-vertical: 1;
    scrollbar-color: #2a3155;
    scrollbar-background: #090c17;
}
.card {
    width: 100%;
    height: auto;
    margin-bottom: 1;
}
.section {
    color: #59618a;
    text-style: bold;
    margin-bottom: 0;
}
.card-body {
    color: #c8c9e8;
}
#exclude-btn {
    width: 100%;
    height: 1;
    min-width: 0;
    padding: 0 1;
    margin: 0 0 1 0;
    border: none;
    background: #101527;
    color: #8b93b8;
    content-align: left middle;
}
#exclude-btn:hover {
    background: #1a2140;
    color: #e9e9ff;
}
#exclude-btn.excluded {
    color: #fb7185;
    background: #1d0f18;
}
#nav {
    grid-size: 2 4;
    grid-columns: 1fr 1fr;
    grid-rows: 1 1 1 1;
    grid-gutter: 0 1;
    height: 4;
    width: 100%;
}
Button.navbtn {
    width: 1fr;
    height: 1;
    min-width: 0;
    padding: 0 1;
    border: none;
    background: transparent;
    color: #7d86ad;
    content-align: left middle;
}
Button.navbtn:hover {
    background: #151b31;
    color: #e9e9ff;
}
#footer {
    height: 3;
    padding: 0 2;
    background: #080b14;
    border-top: solid #1b2138;
    color: #4f577d;
    layout: vertical;
}
#footer-keys {
    height: 1;
    color: #5c6488;
}
#footer-status {
    height: 1;
    color: #7780a8;
}
#footer-status.error {
    color: #fb7185;
}
#footer-status.busy {
    color: #fbbf24;
}

/* ---------------------------------------------------------------- modals */

ModalScreen {
    background: #03040a 72%;
    align: center middle;
}
.dialog {
    width: 92%;
    height: 88%;
    max-width: 116;
    background: #0a0d19;
    border: round #343d68;
    padding: 1 2;
    layout: vertical;
}
.dialog.wide {
    max-width: 132;
}
.dialog.small {
    width: 70%;
    height: auto;
    max-height: 80%;
}
.dialog.small .dialog-body {
    height: auto;
    max-height: 14;
}
.dialog-head {
    height: 2;
    layout: horizontal;
    align: left middle;
    border-bottom: solid #1f2542;
    margin-bottom: 1;
}
.dialog-title {
    width: 1fr;
    color: #c4b5fd;
    text-style: bold;
}
.dialog-esc {
    width: auto;
    color: #59618a;
}
.dialog-sub {
    color: #7d86ad;
    height: auto;
    margin-bottom: 1;
}
.dialog-body {
    height: 1fr;
}
.dialog-footer {
    height: 3;
    margin-top: 1;
    layout: horizontal;
    align: left middle;
}
.dialog-hint {
    width: 1fr;
    color: #59618a;
    height: 1;
}
#settings-status {
    width: 1fr;
}
#account-summary, #source-info {
    padding: 0 1;
}
#excl-title {
    width: 12;
}
.search-row.slim {
    height: 1;
    margin-bottom: 1;
}
#excl-search {
    height: 1;
    border: none;
    background: #101527;
    padding: 0 1;
}
#excl-search:focus {
    background: #171d36;
}
VerticalScroll {
    scrollbar-color: #2a3155;
    scrollbar-background: #090c17;
}

.grow {
    width: 1fr;
}
Input {
    height: 3;
    border: tall #2a3155;
    background: #0c1020;
    color: #e9e9ff;
    padding: 0 1;
}
Input:focus {
    border: tall #6d4aff;
}
OptionList {
    height: 1fr;
    border: none;
    background: #0c1020;
    padding: 0;
    scrollbar-size-vertical: 1;
    scrollbar-color: #2a3155;
    scrollbar-background: #0c1020;
}
OptionList > .option-list--option {
    padding: 0 1;
}
OptionList > .option-list--option-highlighted {
    background: #2d2266;
    color: #ffffff;
}
OptionList > .option-list--option-hover {
    background: #171d36;
}
.btn {
    height: auto;
    min-width: 10;
    border: none;
    background: #171d33;
    color: #c8c9e8;
    text-style: bold;
    padding: 0 2;
    content-align: center middle;
}
.btn:hover {
    background: #242c4f;
    color: #ffffff;
}
.btn.primary {
    background: #6d4aff;
    color: #ffffff;
}
.btn.primary:hover {
    background: #7c5cff;
}
.btn.danger {
    background: #7f1d35;
    color: #ffe4e9;
}
.btn.danger:hover {
    background: #a12543;
}
.btn.ghost {
    background: transparent;
    color: #8b93b8;
}
.btn.ghost:hover {
    background: #171d33;
    color: #ffffff;
}
.btn.compact {
    height: 1;
    min-width: 0;
    padding: 0 1;
    border: none;
    background: #101527;
    color: #8b93b8;
}
.btn.compact:hover {
    background: #242c52;
    color: #ffffff;
}
.btn.compact.on {
    background: #2d2266;
    color: #e8e3ff;
}
.btn:disabled {
    background: #121628;
    color: #4b5274;
}
.choice {
    height: 1;
    width: 34;
    layout: horizontal;
}
.choice-item {
    height: 1;
    min-width: 0;
    width: auto;
    padding: 0 1;
    margin-right: 1;
    color: #697199;
    background: #101527;
    text-style: bold;
}
.choice-item:hover {
    background: #1a2140;
    color: #e9e9ff;
}
.choice-item.on {
    background: #2d2266;
    color: #ffffff;
}
.toggle {
    width: 7;
    height: 1;
    padding: 0 1;
    background: #101527;
    color: #8b93b8;
    text-style: bold;
}
.toggle:hover {
    background: #1a2140;
}
.toggle.on {
    background: #0d2a24;
    color: #6ee7b7;
}
.toggle.off {
    color: #697199;
}
.toggle-locked {
    color: #4b5274;
}
.setting-row {
    height: 4;
    padding: 0 0;
    border-bottom: solid #151b2e;
    layout: grid;
    grid-size: 2 1;
    grid-columns: 1fr 38;
    align-vertical: middle;
}
.split-left .setting-row {
    grid-columns: 1fr 8;
}
.setting-main {
    width: 1fr;
    height: 3;
    layout: vertical;
    align: left middle;
}
.setting-name {
    color: #d8d9f3;
    text-style: bold;
    height: 1;
}
.setting-desc {
    color: #59618a;
    height: 1;
}
.setting-control {
    width: 100%;
    height: 3;
    layout: horizontal;
    align: right middle;
}
#dns-editor {
    width: 38;
    height: 3;
    layout: horizontal;
    align: right middle;
}
#dns-editor .toggle {
    margin-left: 1;
}
.setting-control Input {
    width: 28;
    height: 1;
    border: none;
    background: #101527;
    color: #e9e9ff;
    padding: 0 1;
}
.setting-control .toggle {
    margin-left: 1;
}
.settings-list {
    height: 1fr;
    padding-right: 1;
    scrollbar-size-vertical: 1;
}
.dns-input {
    width: 30;
    height: 1;
    border: none;
    background: #101527;
    color: #e9e9ff;
    padding: 0 1;
}
.split {
    layout: horizontal;
    height: 1fr;
}
.split-left {
    width: 38;
    height: 1fr;
    padding-right: 2;
    border-right: solid #1f2542;
    layout: vertical;
}
.split-right {
    width: 1fr;
    height: 1fr;
    padding-left: 2;
    layout: vertical;
}
.panel {
    background: #0c1020;
    border: round #242c4c;
    padding: 1;
    height: auto;
}
.metric {
    color: #59618a;
    height: 1;
}
.metric-value {
    color: #e9e9ff;
    text-style: bold;
}
.note {
    color: #59618a;
    height: auto;
}
.warn {
    color: #fbbf24;
    height: auto;
}
.error {
    color: #fb7185;
    height: auto;
}
.ok {
    color: #34d399;
    height: auto;
}
.picker {
    height: 1fr;
    background: #0c1020;
    border: round #242c4c;
    padding: 0 1;
}
.picker-row {
    height: 1;
    layout: horizontal;
}
.picker-label {
    width: 1fr;
    height: 1;
    color: #c8c9e8;
}
.picker-value {
    width: auto;
    color: #a78bfa;
    text-style: bold;
}
.search-row {
    height: 3;
    margin-bottom: 1;
}
.search-row Input {
    width: 1fr;
}
.count-badge {
    width: auto;
    color: #a78bfa;
    background: #171d33;
    padding: 0 1;
    height: 1;
    margin-left: 1;
}
#activity-log {
    height: 1fr;
    background: #0c1020;
    border: round #242c4c;
    padding: 0 1;
}
.help-grid {
    height: 1fr;
    layout: horizontal;
}
.help-col {
    width: 1fr;
    height: 1fr;
    padding-right: 2;
}
.help-key {
    color: #a78bfa;
    text-style: bold;
}
.help-text {
    color: #8b93b8;
}
.tiny {
    color: #4f577d;
    height: auto;
}

/* ------------------------------------------------------------- responsive */

#main.compact #side {
    display: none;
}
#main.compact #tagline {
    display: none;
}
#main.compact #account-label {
    display: none;
}
#main.narrow #map-legend {
    display: none;
}
#main.narrow #actions {
    height: 3;
}
#main.narrow #quick {
    display: none;
}
#main.narrow #primary {
    width: 14;
}
"""


# ===========================================================================
# Configuration and small utilities
# ===========================================================================

DEFAULT_CONFIG: dict[str, Any] = {
    "autoconnect": {
        "enabled": False,
        "preferred": "",
        "excluded": [],
    },
    "features": {
        "p2p": False,
        "securecore": False,
        "tor": False,
        "random": False,
    },
    "source": {},
}


def _deep_merge(default: dict, value: dict) -> dict:
    result = json.loads(json.dumps(default))
    for key, val in (value or {}).items():
        if isinstance(val, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config() -> dict[str, Any]:
    try:
        raw = json.loads(ORBIT_CONFIG_FILE.read_text(encoding="utf-8"))
        cfg = _deep_merge(DEFAULT_CONFIG, raw if isinstance(raw, dict) else {})
    except Exception:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    ac = cfg.setdefault("autoconnect", {})
    ex = ac.get("excluded") or []
    ac["excluded"] = sorted({str(c).upper() for c in ex if isinstance(c, str) and len(c) == 2})
    ac["preferred"] = str(ac.get("preferred") or "").upper()
    feats = cfg.setdefault("features", {})
    for key in DEFAULT_CONFIG["features"]:
        feats[key] = bool(feats.get(key, False))
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    ORBIT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ORBIT_CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, ORBIT_CONFIG_FILE)


def normalize_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_compact(value: int) -> str:
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value/1_000:.1f}K"
    return str(value)


def fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def fmt_distance(km: float) -> str:
    if km < 1:
        return "<1 km"
    if km >= 1000:
        return f"{km:,.0f} km"
    return f"{km:.0f} km"


def clean_output(text: str) -> str:
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text or "")
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


# ===========================================================================
# Data models
# ===========================================================================


@dataclass
class Country:
    code: str
    name: str
    lat: float
    lon: float
    continent: str = ""
    servers: int = 0
    load: int = 0
    features: set[str] = field(default_factory=set)
    cities: dict[str, "City"] = field(default_factory=dict)

    @property
    def has_stats(self) -> bool:
        return self.servers > 0

    @property
    def feature_line(self) -> str:
        order = ["P2P", "SECURE CORE", "TOR"]
        names = [f for f in order if f in self.features]
        return " · ".join(names) if names else "standard"


@dataclass
class City:
    name: str
    lat: float
    lon: float
    servers: int = 0
    load: int = 0
    features: set[str] = field(default_factory=set)


@dataclass
class HomeLocation:
    label: str
    lat: float
    lon: float
    country_code: str = ""
    kind: str = "timezone"


@dataclass
class Connection:
    connected: bool = False
    server_name: str = ""
    location: str = ""
    city: str = ""
    country_name: str = ""
    country_code: str = ""
    entry_country: str = ""
    entry_code: str = ""
    load: int = 0
    protocol: str = ""
    ip: str = ""
    since: float = 0.0
    raw: str = ""

    def reset(self) -> None:
        self.connected = False
        self.server_name = ""
        self.location = ""
        self.city = ""
        self.country_name = ""
        self.country_code = ""
        self.entry_country = ""
        self.entry_code = ""
        self.load = 0
        self.protocol = ""
        self.ip = ""
        self.since = 0.0
        self.raw = ""


@dataclass
class CLIResult:
    cmd: tuple[str, ...]
    code: int
    out: str
    err: str
    seconds: float
    timed_out: bool = False

    @property
    def text(self) -> str:
        if self.out and self.err:
            return f"{self.out}\n{self.err}".strip()
        return (self.out or self.err).strip()

    @property
    def ok(self) -> bool:
        if self.timed_out:
            return False
        if self.code != 0:
            # protonvpn-cli 1.0.5 can return exit code 1 even when the daemon
            # has already torn down the tunnel and printed "Disconnected.".
            if self.cmd[:1] == ("disconnect",) and re.search(
                r"(?im)^\s*(successfully\s+)?disconnected\.?\s*$", self.text
            ):
                return True
            return False
        if re.search(r"(?m)^\s*Error:", self.text):
            return False
        return True

    @property
    def error_text(self) -> str:
        text = self.text
        lines = [line for line in text.splitlines() if line.strip()]
        errors = [line for line in lines if line.lower().startswith(("error:", "usage:"))]
        if errors:
            return "\n".join(errors)
        if self.timed_out:
            return "The protonvpn command timed out. Check your network connection."
        return "\n".join(lines[-8:]) or "The protonvpn command did not return any output."


@dataclass
class ActivityEntry:
    ts: float
    command: str
    ok: bool
    output: str


# ===========================================================================
# CLI parser helpers
# ===========================================================================

COUNTRY_ALIASES = {
    "united states of america": "US",
    "usa": "US",
    "us": "US",
    "united states": "US",
    "united kingdom": "UK",
    "great britain": "UK",
    "england": "UK",
    "uk": "UK",
    "gb": "UK",
    "south korea": "KR",
    "korea": "KR",
    "korea south": "KR",
    "north macedonia": "MK",
    "macedonia": "MK",
    "czechia": "CZ",
    "czech republic": "CZ",
    "ivory coast": "CI",
    "cote d ivoire": "CI",
    "palestine": "PS",
    "palestinian territory": "PS",
    "russia": "RU",
    "türkiye": "TR",
    "turkiye": "TR",
    "turkey": "TR",
    "vatican city": "VA",
    "hong kong": "HK",
    "macao": "MO",
    "macau": "MO",
    "swaziland": "SZ",
    "eswatini": "SZ",
}


def parse_country_table(text: str) -> "OrderedDict[str, str]":
    result: OrderedDict[str, str] = OrderedDict()
    for line in clean_output(text).splitlines():
        match = re.match(r"^\s*(.+?)\s{2,}([A-Za-z]{2})\s*$", line)
        if not match:
            continue
        name, code = match.group(1).strip(), match.group(2).upper()
        if name.lower() in {"country", "setting"}:
            continue
        result[code] = name
    return result


def parse_city_table(text: str) -> list[tuple[str, set[str]]]:
    rows: list[tuple[str, set[str]]] = []
    in_table = False
    for line in clean_output(text).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^City\s+Features$", stripped):
            in_table = True
            continue
        if not in_table:
            continue
        if set(stripped) <= {"-", " "}:
            continue
        match = re.match(r"^(.+?)\s{2,}(.*?)\s*$", line)
        if not match:
            continue
        name = match.group(1).strip()
        raw_features = match.group(2).strip()
        features = {
            part.strip().upper()
            for part in raw_features.split(",")
            if part.strip() and part.strip().lower() != "features"
        }
        rows.append((name, features))
    return rows


def parse_config_table(text: str) -> "OrderedDict[str, str]":
    result: "OrderedDict[str, str]" = OrderedDict()
    in_table = False
    for line in clean_output(text).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("setting") and "value" in stripped.lower():
            in_table = True
            continue
        if not in_table:
            continue
        if set(stripped) <= {"-", " "}:
            continue
        match = re.match(r"^([a-z][a-z0-9-]+)\s{2,}(.+?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2).strip()
        elif stripped.startswith("Use ") or stripped.startswith("To "):
            in_table = False
    return result


def parse_status_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in clean_output(text).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    return fields


def parse_connect_output(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    match = re.search(r"Connected to ([^\s]+) in (.+?)\.", text)
    if match:
        result["server"] = match.group(1)
        result["location"] = match.group(2)
    match = re.search(r"Your new IP address is ([0-9a-fA-F:.]+)\.", text)
    if match:
        result["ip"] = match.group(1)
    return result


def parse_dns_value(raw: str) -> list[str]:
    match = re.search(r"\[([^\]]*)\]", raw or "")
    if not match:
        return []
    return [part.strip() for part in match.group(1).split(",") if part.strip()]


# ===========================================================================
# Source location
# ===========================================================================

TZ_COORDS: dict[str, tuple[float, float, str]] = {
    "UTC": (51.5074, -0.1278, "London"),
    "Etc/UTC": (51.5074, -0.1278, "London"),
    "Europe/London": (51.5074, -0.1278, "London"),
    "Europe/Dublin": (53.3498, -6.2603, "Dublin"),
    "Europe/Lisbon": (38.7223, -9.1393, "Lisbon"),
    "Europe/Madrid": (40.4168, -3.7038, "Madrid"),
    "Europe/Paris": (48.8566, 2.3522, "Paris"),
    "Europe/Brussels": (50.8503, 4.3517, "Brussels"),
    "Europe/Amsterdam": (52.3676, 4.9041, "Amsterdam"),
    "Europe/Luxembourg": (49.6116, 6.1319, "Luxembourg"),
    "Europe/Berlin": (52.5200, 13.4050, "Berlin"),
    "Europe/Zurich": (47.3769, 8.5417, "Zurich"),
    "Europe/Vienna": (48.2082, 16.3738, "Vienna"),
    "Europe/Rome": (41.9028, 12.4964, "Rome"),
    "Europe/Prague": (50.0755, 14.4378, "Prague"),
    "Europe/Warsaw": (52.2297, 21.0122, "Warsaw"),
    "Europe/Budapest": (47.4979, 19.0402, "Budapest"),
    "Europe/Bratislava": (48.1486, 17.1077, "Bratislava"),
    "Europe/Ljubljana": (46.0569, 14.5058, "Ljubljana"),
    "Europe/Zagreb": (45.8150, 15.9819, "Zagreb"),
    "Europe/Belgrade": (44.7866, 20.4489, "Belgrade"),
    "Europe/Sarajevo": (43.8563, 18.4131, "Sarajevo"),
    "Europe/Skopje": (41.9981, 21.4254, "Skopje"),
    "Europe/Tirane": (41.3275, 19.8187, "Tirana"),
    "Europe/Athens": (37.9838, 23.7275, "Athens"),
    "Europe/Sofia": (42.6977, 23.3219, "Sofia"),
    "Europe/Bucharest": (44.4268, 26.1025, "Bucharest"),
    "Europe/Chisinau": (47.0105, 28.8638, "Chisinau"),
    "Europe/Kyiv": (50.4501, 30.5234, "Kyiv"),
    "Europe/Minsk": (53.9006, 27.5590, "Minsk"),
    "Europe/Moscow": (55.7558, 37.6173, "Moscow"),
    "Europe/Istanbul": (41.0082, 28.9784, "Istanbul"),
    "Europe/Stockholm": (59.3293, 18.0686, "Stockholm"),
    "Europe/Oslo": (59.9139, 10.7522, "Oslo"),
    "Europe/Copenhagen": (55.6761, 12.5683, "Copenhagen"),
    "Europe/Helsinki": (60.1699, 24.9384, "Helsinki"),
    "Europe/Tallinn": (59.4370, 24.7536, "Tallinn"),
    "Europe/Riga": (56.9496, 24.1052, "Riga"),
    "Europe/Vilnius": (54.6872, 25.2797, "Vilnius"),
    "Europe/Reykjavik": (64.1466, -21.9426, "Reykjavik"),
    "Asia/Seoul": (37.5665, 126.9780, "Seoul"),
    "Asia/Pyongyang": (39.0392, 125.7625, "Pyongyang"),
    "Asia/Tokyo": (35.6762, 139.6503, "Tokyo"),
    "Asia/Shanghai": (31.2304, 121.4737, "Shanghai"),
    "Asia/Hong_Kong": (22.3193, 114.1694, "Hong Kong"),
    "Asia/Taipei": (25.0330, 121.5654, "Taipei"),
    "Asia/Singapore": (1.3521, 103.8198, "Singapore"),
    "Asia/Kuala_Lumpur": (3.1390, 101.6869, "Kuala Lumpur"),
    "Asia/Bangkok": (13.7563, 100.5018, "Bangkok"),
    "Asia/Ho_Chi_Minh": (10.8231, 106.6297, "Ho Chi Minh City"),
    "Asia/Jakarta": (-6.2088, 106.8456, "Jakarta"),
    "Asia/Manila": (14.5995, 120.9842, "Manila"),
    "Asia/Kolkata": (22.5726, 88.3639, "Kolkata"),
    "Asia/Calcutta": (22.5726, 88.3639, "Kolkata"),
    "Asia/Dhaka": (23.8103, 90.4125, "Dhaka"),
    "Asia/Karachi": (24.8607, 67.0011, "Karachi"),
    "Asia/Kathmandu": (27.7172, 85.3240, "Kathmandu"),
    "Asia/Colombo": (6.9271, 79.8612, "Colombo"),
    "Asia/Yangon": (16.8409, 96.1735, "Yangon"),
    "Asia/Dubai": (25.2048, 55.2708, "Dubai"),
    "Asia/Riyadh": (24.7136, 46.6753, "Riyadh"),
    "Asia/Qatar": (25.2854, 51.5310, "Doha"),
    "Asia/Kuwait": (29.3759, 47.9774, "Kuwait City"),
    "Asia/Bahrain": (26.2285, 50.5860, "Manama"),
    "Asia/Muscat": (23.5880, 58.3829, "Muscat"),
    "Asia/Tehran": (35.6892, 51.3890, "Tehran"),
    "Asia/Baghdad": (33.3152, 44.3661, "Baghdad"),
    "Asia/Beirut": (33.8938, 35.5018, "Beirut"),
    "Asia/Amman": (31.9539, 35.9106, "Amman"),
    "Asia/Damascus": (33.5138, 36.2765, "Damascus"),
    "Asia/Jerusalem": (31.7683, 35.2137, "Jerusalem"),
    "Asia/Baku": (40.4093, 49.8671, "Baku"),
    "Asia/Tbilisi": (41.7151, 44.8271, "Tbilisi"),
    "Asia/Yerevan": (40.1792, 44.4991, "Yerevan"),
    "Asia/Almaty": (43.2220, 76.8512, "Almaty"),
    "Asia/Tashkent": (41.2995, 69.2401, "Tashkent"),
    "Asia/Bishkek": (42.8746, 74.5698, "Bishkek"),
    "Asia/Dushanbe": (38.5598, 68.7870, "Dushanbe"),
    "Asia/Ashgabat": (37.9601, 58.3261, "Ashgabat"),
    "Asia/Kabul": (34.5553, 69.2075, "Kabul"),
    "Africa/Cairo": (30.0444, 31.2357, "Cairo"),
    "Africa/Casablanca": (33.5731, -7.5898, "Casablanca"),
    "Africa/Algiers": (36.7538, 3.0588, "Algiers"),
    "Africa/Tunis": (36.8065, 10.1815, "Tunis"),
    "Africa/Tripoli": (32.8872, 13.1913, "Tripoli"),
    "Africa/Lagos": (6.5244, 3.3792, "Lagos"),
    "Africa/Accra": (5.6037, -0.1870, "Accra"),
    "Africa/Abidjan": (5.3599, -4.0083, "Abidjan"),
    "Africa/Dakar": (14.7167, -17.4677, "Dakar"),
    "Africa/Nairobi": (-1.2921, 36.8219, "Nairobi"),
    "Africa/Addis_Ababa": (8.9806, 38.7578, "Addis Ababa"),
    "Africa/Johannesburg": (-26.2041, 28.0473, "Johannesburg"),
    "Africa/Khartoum": (15.5007, 32.5599, "Khartoum"),
    "Africa/Kinshasa": (-4.4419, 15.2663, "Kinshasa"),
    "Africa/Luanda": (-8.8390, 13.2894, "Luanda"),
    "Africa/Dar_es_Salaam": (-6.7924, 39.2083, "Dar es Salaam"),
    "Africa/Kampala": (0.3476, 32.5825, "Kampala"),
    "Africa/Kigali": (-1.9441, 30.0619, "Kigali"),
    "Africa/Maputo": (-25.9692, 32.5732, "Maputo"),
    "Africa/Harare": (-17.8252, 31.0335, "Harare"),
    "America/New_York": (40.7128, -74.0060, "New York"),
    "America/Chicago": (41.8781, -87.6298, "Chicago"),
    "America/Denver": (39.7392, -104.9903, "Denver"),
    "America/Los_Angeles": (34.0522, -118.2437, "Los Angeles"),
    "America/Phoenix": (33.4484, -112.0740, "Phoenix"),
    "America/Anchorage": (61.2181, -149.9003, "Anchorage"),
    "America/Toronto": (43.6532, -79.3832, "Toronto"),
    "America/Vancouver": (49.2827, -123.1207, "Vancouver"),
    "America/Mexico_City": (19.4326, -99.1332, "Mexico City"),
    "America/Bogota": (4.7110, -74.0721, "Bogota"),
    "America/Lima": (-12.0464, -77.0428, "Lima"),
    "America/Santiago": (-33.4489, -70.6693, "Santiago"),
    "America/Argentina/Buenos_Aires": (-34.6037, -58.3816, "Buenos Aires"),
    "America/Sao_Paulo": (-23.5505, -46.6333, "Sao Paulo"),
    "America/Caracas": (10.4806, -66.9036, "Caracas"),
    "America/Panama": (8.9824, -79.5199, "Panama City"),
    "America/Havana": (23.1136, -82.3666, "Havana"),
    "America/Santo_Domingo": (18.4861, -69.9312, "Santo Domingo"),
    "America/Puerto_Rico": (18.4655, -66.1057, "San Juan"),
    "Pacific/Auckland": (-36.8485, 174.7633, "Auckland"),
    "Australia/Sydney": (-33.8688, 151.2093, "Sydney"),
    "Australia/Melbourne": (-37.8136, 144.9631, "Melbourne"),
    "Australia/Brisbane": (-27.4698, 153.0251, "Brisbane"),
    "Australia/Perth": (-31.9505, 115.8605, "Perth"),
    "Australia/Adelaide": (-34.9285, 138.6007, "Adelaide"),
    "Pacific/Honolulu": (21.3069, -157.8583, "Honolulu"),
    "Pacific/Fiji": (-18.1416, 178.4419, "Suva"),
}


def read_timezone_name() -> str:
    try:
        value = Path("/etc/timezone").read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    env_tz = os.environ.get("TZ", "").strip().lstrip(":")
    if env_tz:
        return env_tz
    try:
        tzinfo = datetime.now().astimezone().tzinfo
        key = getattr(tzinfo, "key", None)
        if key:
            return key
        name = getattr(tzinfo, "tzname", None)
        if name:
            return name
    except Exception:
        pass
    return "UTC"


def timezone_home() -> HomeLocation:
    zone = read_timezone_name()
    if zone in TZ_COORDS:
        lat, lon, label = TZ_COORDS[zone]
        return HomeLocation(label=label, lat=lat, lon=lon, kind="timezone")
    # Unknown zone: estimate longitude from the UTC offset.
    try:
        offset = datetime.now().astimezone().utcoffset()
        hours = (offset.total_seconds() / 3600.0) if offset else 0.0
    except Exception:
        hours = 0.0
    lon = max(-180.0, min(180.0, hours * 15.0))
    label = f"UTC{hours:+05.1f}" if hours else "UTC"
    return HomeLocation(label=label, lat=45.0, lon=lon, kind="timezone")


def fetch_ip_home(timeout: float = 6.0) -> Optional[HomeLocation]:
    """Best-effort physical location lookup. Never called automatically."""
    try:
        req = Request(
            "https://ipinfo.io/json",
            headers={"User-Agent": f"{APP_TITLE}/{APP_VERSION}"},
        )
        with urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
        loc = (data.get("loc") or "").split(",")
        if len(loc) != 2:
            return None
        lat, lon = float(loc[0]), float(loc[1])
        label = data.get("city") or data.get("region") or data.get("country") or "Local"
        return HomeLocation(
            label=str(label),
            lat=lat,
            lon=lon,
            country_code=str(data.get("country") or "").upper(),
            kind="ip",
        )
    except Exception:
        return None


# ===========================================================================
# CLI runner
# ===========================================================================


class CLIRunner:
    """Serialized async wrapper around the installed protonvpn executable."""

    def __init__(
        self,
        path: Optional[str],
        recorder: Optional[Callable[[ActivityEntry], None]] = None,
    ) -> None:
        self.path = path
        self.recorder = recorder
        self.lock = asyncio.Lock()
        self.current_command = ""
        self.last_result: Optional[CLIResult] = None

    @property
    def busy(self) -> bool:
        return self.lock.locked()

    async def run(
        self,
        *args: str,
        timeout: float = 120.0,
        record: bool = True,
    ) -> CLIResult:
        cmd = tuple(args)
        display = f"{PROGRAM} {' '.join(args)}".strip()
        started = time.monotonic()
        async with self.lock:
            self.current_command = display
            if not self.path:
                result = CLIResult(
                    cmd=cmd,
                    code=127,
                    out="",
                    err=f"Error: '{PROGRAM}' was not found in PATH. Install proton-vpn-cli "
                    "or set PROTONVPN_BIN to its executable path.",
                    seconds=0.0,
                )
            else:
                env = os.environ.copy()
                env.update(
                    {
                        "NO_COLOR": "1",
                        "CLICOLOR": "0",
                        "TERM": "dumb",
                        "PYTHONUNBUFFERED": "1",
                    }
                )
                try:
                    proc = await asyncio.create_subprocess_exec(
                        self.path,
                        *args,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                        start_new_session=True,
                    )
                except Exception as exc:
                    result = CLIResult(
                        cmd=cmd,
                        code=126,
                        out="",
                        err=f"Error: could not execute {self.path}: {exc}",
                        seconds=time.monotonic() - started,
                    )
                else:
                    timed_out = False
                    try:
                        raw_out, raw_err = await asyncio.wait_for(proc.communicate(), timeout)
                    except asyncio.TimeoutError:
                        timed_out = True
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        except Exception:
                            try:
                                proc.kill()
                            except Exception:
                                pass
                        try:
                            await proc.wait()
                        except Exception:
                            pass
                        raw_out, raw_err = b"", b""
                    result = CLIResult(
                        cmd=cmd,
                        code=proc.returncode if proc.returncode is not None else -1,
                        out=clean_output(raw_out.decode("utf-8", "replace")),
                        err=clean_output(raw_err.decode("utf-8", "replace")),
                        seconds=time.monotonic() - started,
                        timed_out=timed_out,
                    )
            self.last_result = result
            self.current_command = ""
        if record and self.recorder is not None:
            output = result.text
            if result.timed_out:
                output = f"{output}\n(timed out after {timeout:.0f}s)".strip()
            self.recorder(
                ActivityEntry(
                    ts=time.time(),
                    command=display,
                    ok=result.ok,
                    output=output[:20000],
                )
            )
        return result


# ===========================================================================
# Robinson projection and braille canvas
# ===========================================================================

WORLD_W = 1000.0
WORLD_H = 507.0
ROB_XR = 2.6660
ROB_YR = 1.3523

ROB_X = [
    1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730,
    0.9600, 0.9427, 0.9216, 0.8962, 0.8679, 0.8350,
    0.7986, 0.7597, 0.7186, 0.6732, 0.6213, 0.5722, 0.5322,
]
ROB_Y = [
    0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100,
    0.3720, 0.4340, 0.4958, 0.5571, 0.6176, 0.6769,
    0.7346, 0.7903, 0.8435, 0.8936, 0.9394, 0.9761, 1.0000,
]


def _robinson_coeff(lat: float) -> tuple[float, float]:
    a = min(abs(lat), 90.0) / 5.0
    index = int(a)
    if index >= 18:
        return ROB_X[18], ROB_Y[18]
    frac = a - index
    return (
        ROB_X[index] * (1 - frac) + ROB_X[index + 1] * frac,
        ROB_Y[index] * (1 - frac) + ROB_Y[index + 1] * frac,
    )


def robinson_forward(lat: float, lon: float) -> tuple[float, float]:
    """Return world coordinates in a 1000 x 507 virtual canvas."""
    cx, cy = _robinson_coeff(lat)
    x = 0.8487 * math.radians(lon) * cx
    y = 1.3523 * cy * (1.0 if lat >= 0 else -1.0)
    return (
        (x + ROB_XR) / (2 * ROB_XR) * WORLD_W,
        (ROB_YR - y) / (2 * ROB_YR) * WORLD_H,
    )


def robinson_inverse(x: float, y: float) -> tuple[float, float]:
    """Inverse of robinson_forward; returns (lat, lon)."""
    yr = ROB_YR - (y / WORLD_H) * (2 * ROB_YR)
    ay = min(abs(yr) / ROB_YR, 1.0)
    lat = 90.0
    for index in range(18):
        if ROB_Y[index] <= ay <= ROB_Y[index + 1]:
            span = ROB_Y[index + 1] - ROB_Y[index]
            frac = (ay - ROB_Y[index]) / span if span else 0.0
            lat = (index + frac) * 5.0
            break
    if yr < 0:
        lat = -lat
    cx, _ = _robinson_coeff(lat)
    xr = (x / WORLD_W) * (2 * ROB_XR) - ROB_XR
    lon = math.degrees(xr / (0.8487 * cx)) if cx else 0.0
    return max(-90.0, min(90.0, lat)), max(-180.0, min(180.0, lon))


DOT_BITS = {
    (0, 0): 0x01,
    (0, 1): 0x02,
    (0, 2): 0x04,
    (1, 0): 0x08,
    (1, 1): 0x10,
    (1, 2): 0x20,
    (0, 3): 0x40,
    (1, 3): 0x80,
}

LAND_MASK = zlib.decompress(base64.b85decode(LAND_MASK_B85))
BORDER_MASK = zlib.decompress(base64.b85decode(BORDER_MASK_B85))


def _mask_bit(mask: bytes, width: int, height: int, x: int, y: int) -> int:
    if x < 0 or x >= width or y < 0 or y >= height:
        return 0
    index = y * width + x
    return (mask[index >> 3] >> (7 - (index & 7))) & 1


def land_bit(lon: float, lat: float) -> int:
    x = int((lon + 180.0) / 360.0 * LAND_W) % LAND_W
    y = int((90.0 - lat) / 180.0 * LAND_H)
    return _mask_bit(LAND_MASK, LAND_W, LAND_H, x, y)


def border_bit(lon: float, lat: float) -> int:
    x = int((lon + 180.0) / 360.0 * LAND_W) % LAND_W
    y = int((90.0 - lat) / 180.0 * LAND_H)
    return _mask_bit(BORDER_MASK, LAND_W, LAND_H, x, y)


@dataclass
class MapGeometry:
    width: int
    height: int
    center_x: float = WORLD_W / 2
    center_y: float = WORLD_H / 2
    span: float = WORLD_W

    @property
    def px_width(self) -> int:
        return max(1, self.width * 2)

    @property
    def px_height(self) -> int:
        return max(1, self.height * 4)

    @property
    def span_y(self) -> float:
        return self.span * (self.px_height / self.px_width)

    @property
    def x0(self) -> float:
        return self.center_x - self.span / 2

    @property
    def y0(self) -> float:
        return self.center_y - self.span_y / 2

    def clamped(self) -> "MapGeometry":
        span = max(80.0, min(1100.0, self.span))
        span_y = span * (self.px_height / self.px_width)
        center_y = self.center_y
        if span_y >= WORLD_H - 0.5:
            center_y = WORLD_H / 2
        else:
            center_y = max(span_y / 2, min(WORLD_H - span_y / 2, center_y))
        center_x = max(span / 2, min(WORLD_W - span / 2, self.center_x))
        return MapGeometry(self.width, self.height, center_x, center_y, span)

    def project_world(self, wx: float, wy: float) -> tuple[float, float]:
        return (
            (wx - self.x0) / self.span * self.px_width,
            (wy - self.y0) / self.span_y * self.px_height,
        )

    def project(self, lat: float, lon: float) -> tuple[float, float]:
        wx, wy = robinson_forward(lat, lon)
        return self.project_world(wx, wy)

    def unproject(self, px: float, py: float) -> tuple[float, float]:
        wx = self.x0 + (px / self.px_width) * self.span
        wy = self.y0 + (py / self.px_height) * self.span_y
        return robinson_inverse(wx, wy)

    def cell(self, lat: float, lon: float) -> tuple[int, int]:
        px, py = self.project(lat, lon)
        return int(px // 2), int(py // 4)

    def in_view(self, lat: float, lon: float, margin: float = 0.0) -> bool:
        px, py = self.project(lat, lon)
        return (
            -margin <= px <= self.px_width + margin
            and -margin <= py <= self.px_height + margin
        )


def make_geometry(
    width: int,
    height: int,
    center_x: float = WORLD_W / 2,
    center_y: float = WORLD_H / 2,
    span: float = WORLD_W,
) -> MapGeometry:
    if width < 2 or height < 2:
        return MapGeometry(max(1, width), max(1, height), center_x, center_y, span)
    return MapGeometry(width, height, center_x, center_y, span).clamped()


def cell_land_samples(geo: MapGeometry, cx: int, cy: int) -> tuple[int, int, int]:
    """Return (braille mask, land count, border count) for a terminal cell."""
    mask = 0
    land_count = 0
    border_count = 0
    base_x = cx * 2
    base_y = cy * 4
    for dx in (0, 1):
        for dy in (0, 1, 2, 3):
            px = base_x + dx + 0.5
            py = base_y + dy + 0.5
            lat, lon = geo.unproject(px, py)
            if land_bit(lon, lat):
                mask |= DOT_BITS[(dx, dy)]
                land_count += 1
            if border_bit(lon, lat):
                border_count += 1
    return mask, land_count, border_count


# ===========================================================================
# Server-list cache enrichment
# ===========================================================================

FEATURE_BITS = {
    1: "SECURE CORE",
    2: "TOR",
    4: "P2P",
    8: "STREAMING",
    16: "IPV6",
}


def _features_from_bits(bits: int) -> set[str]:
    return {name for flag, name in FEATURE_BITS.items() if bits & flag}


def build_server_index(source: Path) -> dict[str, Any]:
    data = json.loads(source.read_text(encoding="utf-8"))
    logical = data.get("LogicalServers") or []
    countries: dict[str, Any] = {}
    for server in logical:
        code = (server.get("ExitCountry") or server.get("EntryCountry") or "").upper()
        if not code:
            continue
        city_name = (server.get("City") or "").strip()
        loc = server.get("ExitLocation") or {}
        lat = loc.get("Latitude")
        lon = loc.get("Longitude")
        features = _features_from_bits(int(server.get("Features") or 0))
        load = int(server.get("Load") or 0)
        entry = (server.get("EntryCountry") or "").upper()
        country = countries.setdefault(
            code,
            {"servers": 0, "load_total": 0, "features": set(), "cities": {}},
        )
        country["servers"] += 1
        country["load_total"] += load
        country["features"].update(features)
        if city_name:
            city = country["cities"].setdefault(
                city_name,
                {
                    "servers": 0,
                    "load_total": 0,
                    "features": set(),
                    "lat": lat,
                    "lon": lon,
                },
            )
            city["servers"] += 1
            city["load_total"] += load
            city["features"].update(features)
            if city.get("lat") is None and lat is not None:
                city["lat"] = lat
            if city.get("lon") is None and lon is not None:
                city["lon"] = lon
        # Secure Core entries: remember the entry country on the country record.
        if entry and entry != code:
            country.setdefault("entries", set()).add(entry)
    # Make it JSON-serializable and turn sets into sorted lists.
    out_countries: dict[str, Any] = {}
    for code, country in countries.items():
        count = max(1, country["servers"])
        out_cities: dict[str, Any] = {}
        for name, city in country["cities"].items():
            out_cities[name] = {
                "servers": city["servers"],
                "load": round(city["load_total"] / max(1, city["servers"])),
                "features": sorted(city["features"]),
                "lat": city.get("lat"),
                "lon": city.get("lon"),
            }
        out_countries[code] = {
            "servers": country["servers"],
            "load": round(country["load_total"] / count),
            "features": sorted(country["features"]),
            "cities": out_cities,
            "entries": sorted(country.get("entries", set())),
        }
    return {
        "source_mtime": source.stat().st_mtime,
        "source_size": source.stat().st_size,
        "countries": out_countries,
    }


def load_server_index_cache() -> Optional[dict[str, Any]]:
    try:
        data = json.loads(ORBIT_INDEX_CACHE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "countries" not in data:
            return None
        return data
    except Exception:
        return None


def cache_is_fresh(index: Optional[dict[str, Any]], source: Path) -> bool:
    if not index or not source.exists():
        return False
    try:
        stat = source.stat()
        return (
            abs(float(index.get("source_mtime", 0)) - stat.st_mtime) < 1.0
            and int(index.get("source_size", 0)) == stat.st_size
        )
    except Exception:
        return False


def apply_server_index(countries: dict[str, Country], index: dict[str, Any]) -> None:
    for code, stats in (index.get("countries") or {}).items():
        country = countries.get(code)
        if country is None:
            continue
        country.servers = int(stats.get("servers") or 0)
        country.load = int(stats.get("load") or 0)
        country.features = set(stats.get("features") or [])
        city_data = stats.get("cities") or {}
        for name, info in city_data.items():
            features = set(info.get("features") or [])
            lat = info.get("lat")
            lon = info.get("lon")
            if lat is None or lon is None:
                continue
            country.cities[name] = City(
                name=name,
                lat=float(lat),
                lon=float(lon),
                servers=int(info.get("servers") or 0),
                load=int(info.get("load") or 0),
                features=features,
            )


# ===========================================================================
# Shared UI helpers
# ===========================================================================


def markup(text: str) -> str:
    """Escape untrusted text for Textual/Rich markup."""
    return markup_escape(str(text))


def status_bits(app: "OrbitApp") -> tuple[str, str]:
    if app.busy:
        return "busy", "◌ " + (app.busy_message or "WORKING").upper()
    if app.connection.connected:
        label = "● CONNECTED"
        if app.connection.server_name:
            label += "  " + app.connection.server_name
        return "connected", label
    if app.signed_in is False:
        return "disconnected", "◇ SIGNED OUT"
    return "disconnected", "○ DISCONNECTED"


def signin_outcome(
    returncode: int,
    signed_in: Optional[bool],
    was_signed_in: bool,
    previous_account: str,
    account_name: str,
    error_detail: str = "",
) -> tuple[bool, str]:
    """Translate a finished interactive sign-in into a UI result.

    The CLI exit code and the freshly refreshed account state are both
    considered so a failed attempt never reports success just because an
    older session was still present.
    """
    detail = clean_output(error_detail)
    detail = detail.splitlines()[0].strip() if detail else ""
    if len(detail) > 160:
        detail = detail[:157].rstrip() + "…"
    if returncode == 0 and signed_in:
        return True, "Signed in. Welcome back."
    if returncode != 0:
        if signed_in and was_signed_in and account_name == previous_account:
            message = f"Sign-in failed (CLI exit code {returncode}); existing session unchanged."
            return False, f"{detail} {message}".strip() if detail else message
        if detail:
            return False, f"Sign-in failed: {detail}"
        return (
            False,
            f"Sign-in failed (CLI exit code {returncode}). Check the CLI output above.",
        )
    return False, "Sign-in did not complete. Check the CLI output above and try again."


# ===========================================================================
# Small custom controls
# ===========================================================================


class BigAction(Static):
    """A three-row action target.

    Textual's Button has an internal line-pad quirk when forced to exactly
    three rows (the label is clipped).  A Static gives us a stable, large
    primary control with the same mouse affordance.
    """

    can_focus = False

    class Pressed(Message):
        def __init__(self, action: "BigAction") -> None:
            self.action = action
            super().__init__()

    def __init__(self, label: str, *, id: str | None = None, classes: str | None = None) -> None:
        self.label_text = label
        super().__init__(label, markup=False, id=id, classes=classes)

    def set_label(self, label: str) -> None:
        if label != self.label_text:
            self.label_text = label
            self.update(label, layout=True)

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Pressed(self))


class Pill(Static):
    """A clickable feature pill used above the Connect button."""

    can_focus = False

    class Changed(Message):
        def __init__(self, pill: "Pill", active: bool) -> None:
            self.pill = pill
            self.active = active
            super().__init__()

    def __init__(self, key: str, label: str, active: bool = False, **kwargs: Any) -> None:
        self.key = key
        self.label_text = label
        self.active = active
        super().__init__("", markup=False, **kwargs)
        self._sync()

    def _sync(self) -> None:
        self.update(f"{'●' if self.active else '○'} {self.label_text}")
        self.set_class(self.active, "on")

    def set_active(self, active: bool, notify: bool = False) -> None:
        if self.active == active:
            return
        self.active = active
        self._sync()
        if notify:
            self.post_message(self.Changed(self, self.active))

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Changed(self, not self.active))


class Toggle(Static):
    """A compact on/off control with a clear keyboard/mouse target."""

    can_focus = False

    class Changed(Message):
        def __init__(self, toggle: "Toggle", value: bool) -> None:
            self.toggle = toggle
            self.value = value
            super().__init__()

    def __init__(
        self,
        value: bool = False,
        *,
        on_label: str = "ON",
        off_label: str = "OFF",
        locked: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self.value = bool(value)
        self.on_label = on_label
        self.off_label = off_label
        self.locked = locked
        classes = f"toggle {classes}".strip() if classes else "toggle"
        super().__init__("", markup=False, name=name, id=id, classes=classes)
        self._sync()

    def _sync(self) -> None:
        self.update(f"{'◉' if self.value else '○'} {self.on_label if self.value else self.off_label}")
        self.set_class(self.value, "on")
        self.set_class(not self.value, "off")
        self.set_class(self.locked, "toggle-locked")

    def set_value(self, value: bool, notify: bool = False) -> None:
        if self.value == value:
            return
        self.value = bool(value)
        self._sync()
        if notify:
            self.post_message(self.Changed(self, self.value))

    def on_click(self, event: events.Click) -> None:
        event.stop()
        if self.locked:
            return
        value = not self.value
        self.set_value(value)
        self.post_message(self.Changed(self, value))


class Choice(Widget):
    """A segmented selector (used for NetShield and Kill Switch modes)."""

    can_focus = False

    class Changed(Message):
        def __init__(self, choice: "Choice", value: str) -> None:
            self.choice = choice
            self.value = value
            super().__init__()

    def __init__(
        self,
        key: str,
        options: list[tuple[str, str]],
        value: str,
        *,
        locked: bool = False,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self.key = key
        self.options = options
        self.value = value
        self.locked = locked
        self._items: list[Static] = []
        classes = f"choice {classes}".strip() if classes else "choice"
        super().__init__(id=id, classes=classes)

    def compose(self) -> ComposeResult:
        for index, (_, label) in enumerate(self.options):
            yield Static(
                label,
                id=f"choice-{self.key}-{index}",
                classes="choice-item",
                markup=False,
            )

    def on_mount(self) -> None:
        self._items = [
            self.query_one(f"#choice-{self.key}-{index}", Static)
            for index in range(len(self.options))
        ]
        self._sync()

    def _sync(self) -> None:
        for (value, _), item in zip(self.options, self._items):
            item.set_class(value == self.value, "on")
            item.set_class(self.locked, "toggle-locked")

    def set_value(self, value: str, notify: bool = False) -> None:
        if value == self.value:
            return
        self.value = value
        self._sync()
        if notify:
            self.post_message(self.Changed(self, self.value))

    def set_locked(self, locked: bool) -> None:
        self.locked = locked
        self._sync()

    def on_click(self, event: events.Click) -> None:
        widget = event.widget
        if not isinstance(widget, Static) or not widget.id:
            return
        prefix = f"choice-{self.key}-"
        if not widget.id.startswith(prefix):
            return
        event.stop()
        if self.locked:
            return
        try:
            index = int(widget.id[len(prefix):])
        except ValueError:
            return
        if 0 <= index < len(self.options):
            value = self.options[index][0]
            self.set_value(value)
            self.post_message(self.Changed(self, value))


# ===========================================================================
# Animated world map
# ===========================================================================


@dataclass
class Paint:
    mask: int = 0
    fg: str = ""
    bg: Optional[str] = None
    priority: int = 0
    char: Optional[str] = None
    bold: bool = False


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(v))) for v in rgb])


def lerp_color(color_a: str, color_b: str, t: float) -> str:
    a = _hex_to_rgb(color_a)
    b = _hex_to_rgb(color_b)
    return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


class MapView(Widget):
    """The animated braille world map.

    Land and borders are rendered from embedded Natural Earth data.  Countries
    are plotted at Natural Earth label points; the active route is drawn as a
    travelling dashed arc with a pulse.  The map supports click/hover, arrow-key
    navigation, wheel zoom and selecting any region.
    """

    can_focus = True
    ALLOW_SELECT = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.geo: Optional[MapGeometry] = None
        self.view_center_x = WORLD_W / 2
        self.view_center_y = WORLD_H / 2
        self.view_span = WORLD_W
        self._base_key: Optional[tuple[Any, ...]] = None
        self._base_masks: list[int] = []
        self._base_colors: list[Optional[str]] = []
        self._styles: dict[tuple[str, Optional[str], bool], Style] = {}
        self._hover_code: Optional[str] = None
        self._hover_text = ""
        self._phase = 0.0
        self._last_tick = 0.0
        self._timer = None

    def on_mount(self) -> None:
        self._last_tick = time.monotonic()
        self._timer = self.set_interval(0.12, self._tick)
        self.focus()

    def _tick(self) -> None:
        now = time.monotonic()
        self._phase = now
        if self.is_mounted:
            self.refresh()

    def on_resize(self, event: events.Resize) -> None:
        self._base_key = None
        self.refresh()

    def _ensure_geo(self) -> MapGeometry:
        width = max(1, self.size.width)
        height = max(1, self.size.height)
        key = (width, height)
        if self.geo is None or (self.geo.width, self.geo.height) != key:
            self.geo = make_geometry(
                width,
                height,
                self.view_center_x,
                self.view_center_y,
                self.view_span,
            )
            self._base_key = None
        return self.geo

    def _style(self, fg: str, bg: Optional[str] = None, bold: bool = False) -> Style:
        key = (fg, bg, bold)
        style = self._styles.get(key)
        if style is None:
            style = Style(color=fg, bgcolor=bg, bold=bold)
            self._styles[key] = style
        return style

    # ------------------------------------------------------------- land cache

    def _build_base(self, geo: MapGeometry) -> None:
        width, height = geo.width, geo.height
        masks = [0] * (width * height)
        colors: list[Optional[str]] = [None] * (width * height)
        for cy in range(height):
            row_offset = cy * width
            for cx in range(width):
                mask, land_count, borders = cell_land_samples(geo, cx, cy)
                if not mask and not land_count:
                    continue
                index = row_offset + cx
                masks[index] = mask
                # Political borders are not drawn at world scale: the 1px
                # Natural Earth border raster aliases into long dotted lines
                # at this resolution. Coastlines carry the shape instead.
                if land_count < 8:
                    colors[index] = COL["land_hi"]
                else:
                    colors[index] = COL["land"]
        self._base_masks = masks
        self._base_colors = colors

    # ---------------------------------------------------------------- painting

    @staticmethod
    def _paint_dot(
        ov: dict[int, Paint],
        geo: MapGeometry,
        px: int,
        py: int,
        color: str,
        priority: int,
    ) -> None:
        if px < 0 or py < 0 or px >= geo.px_width or py >= geo.px_height:
            return
        cx, cy = px // 2, py // 4
        if cx < 0 or cy < 0 or cx >= geo.width or cy >= geo.height:
            return
        bit = DOT_BITS[(px % 2, py % 4)]
        index = cy * geo.width + cx
        paint = ov.get(index)
        if paint is None:
            ov[index] = Paint(mask=bit, fg=color, priority=priority)
            return
        if paint.priority > priority:
            return
        if paint.priority < priority:
            ov[index] = Paint(mask=bit, fg=color, priority=priority)
            return
        paint.mask |= bit
        paint.fg = color

    @classmethod
    def _paint_line(
        cls,
        ov: dict[int, Paint],
        geo: MapGeometry,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        color: str,
        priority: int,
    ) -> None:
        dx = x1 - x0
        dy = y1 - y0
        steps = max(1, int(max(abs(dx), abs(dy))))
        for step in range(steps + 1):
            t = step / steps
            cls._paint_dot(
                ov,
                geo,
                round(x0 + dx * t),
                round(y0 + dy * t),
                color,
                priority,
            )

    @classmethod
    def _paint_disk(
        cls,
        ov: dict[int, Paint],
        geo: MapGeometry,
        px: float,
        py: float,
        radius: float,
        color: str,
        priority: int,
    ) -> None:
        r = max(0.0, radius)
        x0, x1 = int(math.floor(px - r)), int(math.ceil(px + r))
        y0, y1 = int(math.floor(py - r)), int(math.ceil(py + r))
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if (xx - px) ** 2 + (yy - py) ** 2 <= r * r:
                    cls._paint_dot(ov, geo, xx, yy, color, priority)

    @classmethod
    def _paint_ring(
        cls,
        ov: dict[int, Paint],
        geo: MapGeometry,
        px: float,
        py: float,
        radius: float,
        color: str,
        priority: int,
        width: float = 1.2,
    ) -> None:
        if radius <= 0:
            return
        outer = radius + width
        x0, x1 = int(math.floor(px - outer)), int(math.ceil(px + outer))
        y0, y1 = int(math.floor(py - outer)), int(math.ceil(py + outer))
        inner = max(0.0, radius - width)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                dist = math.hypot(xx - px, yy - py)
                if inner <= dist <= outer:
                    cls._paint_dot(ov, geo, xx, yy, color, priority)

    # ------------------------------------------------------------------ routes

    def _route_points(
        self,
        geo: MapGeometry,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> list[tuple[float, float, float, float]]:
        """Return bezier segments as (x0, y0, x1, y1, t0, t1) in screen pixels.

        Routes crossing the antimeridian are adjusted to the short side and
        drawn in up to three world copies so the arc can exit one edge and
        enter the other.
        """
        wx1, wy1 = robinson_forward(start[0], start[1])
        wx2, wy2 = robinson_forward(end[0], end[1])
        dx = wx2 - wx1
        if dx > WORLD_W / 2:
            wx2 -= WORLD_W
        elif dx < -WORLD_W / 2:
            wx2 += WORLD_W
        pieces: list[tuple[float, float, float, float, float, float]] = []
        for shift in (-WORLD_W, 0.0, WORLD_W):
            p1 = geo.project_world(wx1 + shift, wy1)
            p2 = geo.project_world(wx2 + shift, wy2)
            # Skip copies that cannot touch the viewport.
            margin = 80
            if max(p1[0], p2[0]) < -margin or min(p1[0], p2[0]) > geo.px_width + margin:
                continue
            if max(p1[1], p2[1]) < -margin or min(p1[1], p2[1]) > geo.px_height + margin:
                continue
            x1, y1 = p1
            x2, y2 = p2
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < 2:
                # Same point (or same city): make a small loop.
                ctrl_x = x1 + max(14, geo.px_width * 0.03)
                ctrl_y = y1 - max(14, geo.px_height * 0.08)
            else:
                mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
                perp_x, perp_y = (y2 - y1) / dist, -(x2 - x1) / dist
                if perp_y > 0:
                    perp_x, perp_y = -perp_x, -perp_y
                offset = min(max(dist * 0.22, 24.0), geo.px_height * 0.46)
                ctrl_x = mid_x + perp_x * offset
                ctrl_y = mid_y + perp_y * offset
            steps = max(24, min(500, int(dist * 1.2) + 24))
            previous: Optional[tuple[float, float]] = None
            for step in range(steps + 1):
                t = step / steps
                one = 1.0 - t
                x = one * one * x1 + 2 * one * t * ctrl_x + t * t * x2
                y = one * one * y1 + 2 * one * t * ctrl_y + t * t * y2
                if previous is not None:
                    pieces.append((previous[0], previous[1], x, y, (step - 1) / steps, t))
                previous = (x, y)
        return [(a, b, c, d, t0, t1) for a, b, c, d, t0, t1 in pieces]

    def _draw_route(
        self,
        ov: dict[int, Paint],
        geo: MapGeometry,
        start: tuple[float, float],
        end: tuple[float, float],
        color_a: str,
        color_b: str,
        *,
        dim: bool = False,
        pulse: bool = True,
        priority: int = 5,
    ) -> None:
        pieces = self._route_points(geo, start, end)
        if not pieces:
            return
        phase = (self._phase * (0.5 if dim else 0.9)) % 1.0
        # A faint continuous underlay makes both previews and live routes easy
        # to follow on a dark terminal.
        for x0, y0, x1, y1, t0, t1 in pieces:
            if geo.px_width <= 0:
                continue
            px = (x0 + x1) / 2
            if px < -4 or px > geo.px_width + 4:
                continue
            self._paint_line(
                ov,
                geo,
                x0,
                y0,
                x1,
                y1,
                "#2a2b4d" if dim else "#1b2746",
                max(3, priority - 1),
            )
        for x0, y0, x1, y1, t0, t1 in pieces:
            dash = (t1 * 3.1 - phase) % 1.0
            if dash >= (0.62 if dim else 0.58):
                continue
            color = lerp_color(color_a, color_b, t1)
            if dim:
                color = lerp_color("#8b7fe0", color, 0.8)
            self._paint_line(ov, geo, x0, y0, x1, y1, color, priority)
        if not pulse:
            return
        # Travelling packet.
        for x0, y0, x1, y1, t0, t1 in pieces:
            local = (self._phase * (0.11 if dim else 0.24)) % 1.0
            if not (t0 <= local <= t1):
                continue
            x = x0 + (x1 - x0) * ((local - t0) / max(1e-9, t1 - t0))
            y = y0 + (y1 - y0) * ((local - t0) / max(1e-9, t1 - t0))
            self._paint_disk(ov, geo, x, y, 2.2, "#f4f1ff", priority + 3)
            self._paint_disk(
                ov,
                geo,
                x,
                y,
                max(3.8, geo.px_width / 100),
                lerp_color(color_a, "#ffffff", 0.45),
                priority,
            )

    # ------------------------------------------------------------------ labels

    def _draw_labels(
        self,
        ov: dict[int, Paint],
        geo: MapGeometry,
        labels: list[tuple[str, float, float, str, str]],
    ) -> None:
        occupied: list[tuple[int, int, int, int]] = []
        width, height = geo.width, geo.height
        for text, lat, lon, fg, bg in labels:
            if not text:
                continue
            px, py = geo.project(lat, lon)
            cx, cy = int(px // 2), int(py // 4)
            max_len = max(0, width - 2)
            if max_len < 4:
                continue
            text = text[:max_len]
            length = len(text)
            source_label = text.lstrip().startswith("◉")
            if source_label:
                candidates = [
                    (cx - length - 2, cy),
                    (cx - length // 2, cy + 1),
                    (cx - length // 2, cy - 2),
                    (cx + 2, cy),
                    (cx + 2, cy - 1),
                    (cx + 1, cy + 2),
                ]
            else:
                candidates = [
                    (cx + 2, cy),
                    (cx + 2, cy - 1),
                    (cx - length - 2, cy),
                    (cx - length - 2, cy - 1),
                    (cx - length // 2, cy - 2),
                    (cx - length // 2, cy + 1),
                    (cx + 1, cy + 2),
                    (cx - length - 1, cy + 2),
                ]
            placed = None
            for x, y in candidates:
                x = max(0, min(width - length, x))
                y = max(0, min(height - 1, y))
                rect = (x, y, x + length, y + 1)
                if any(
                    rect[0] < other[2] and rect[2] > other[0]
                    and rect[1] < other[3] and rect[3] > other[1]
                    for other in occupied
                ):
                    continue
                placed = (x, y)
                occupied.append(rect)
                break
            if placed is None:
                continue
            x, y = placed
            for offset, char in enumerate(text):
                index = y * width + x + offset
                ov[index] = Paint(
                    mask=0,
                    fg=fg,
                    bg=bg,
                    priority=100,
                    char=char,
                    bold=True,
                )

    # ------------------------------------------------------------------ render

    def render(self) -> Text:
        width, height = self.size.width, self.size.height
        if width < 20 or height < 5:
            return Text("Map needs a larger terminal", style=COL["muted"], no_wrap=True)
        geo = self._ensure_geo()
        key = (
            geo.width,
            geo.height,
            round(geo.center_x, 2),
            round(geo.center_y, 2),
            round(geo.span, 2),
        )
        if self._base_key != key:
            self._build_base(geo)
            self._base_key = key

        app: "OrbitApp" = self.app  # type: ignore[assignment]
        overlay: dict[int, Paint] = {}
        labels: list[tuple[str, float, float, str, str]] = []
        home = app.home
        selected = app.selected_country()
        connected = app.connection
        pending = app.pending

        # Destination and route.
        route_start: Optional[tuple[float, float]] = None
        route_end: Optional[tuple[float, float]] = None
        route_label = ""
        route_color_end = COL["violet"]
        entry_place: Optional[tuple[str, float, float]] = None

        if connected.connected and connected.country_code:
            route_start = (home.lat, home.lon)
            dest_country = app.countries.get(connected.country_code)
            dest_lat = dest_country.lat if dest_country else home.lat
            dest_lon = dest_country.lon if dest_country else home.lon
            if connected.city and connected.country_code in app.countries:
                city = app.countries[connected.country_code].cities.get(connected.city)
                if city:
                    dest_lat, dest_lon = city.lat, city.lon
            route_end = (dest_lat, dest_lon)
            route_label = connected.city or connected.country_name or connected.server_name
            route_color_end = COL["green"]
            if connected.entry_code and connected.entry_code != connected.country_code:
                entry_country = app.countries.get(connected.entry_code)
                if entry_country:
                    entry_place = (
                        connected.entry_country or connected.entry_code,
                        entry_country.lat,
                        entry_country.lon,
                    )
        elif pending is not None:
            lat = pending.get("lat")
            lon = pending.get("lon")
            if lat is not None and lon is not None:
                route_start = (home.lat, home.lon)
                route_end = (float(lat), float(lon))
                route_label = str(pending.get("label") or "")
                route_color_end = COL["amber"]
            elif pending.get("scan"):
                candidates = app.scan_candidates()
                if candidates:
                    chosen = candidates[int(self._phase * 1.3) % len(candidates)]
                    route_start = (home.lat, home.lon)
                    route_end = (chosen.lat, chosen.lon)
                    route_label = f"scanning · {chosen.name}"
                    route_color_end = COL["amber"]
        elif selected is not None:
            route_start = (home.lat, home.lon)
            route_end = (selected.lat, selected.lon)
            if app.selected_city_name:
                city = selected.cities.get(app.selected_city_name)
                if city:
                    route_end = (city.lat, city.lon)
            route_label = app.selected_city_name or selected.name
            route_color_end = COL["violet"]

        if route_start and route_end:
            if entry_place:
                self._draw_route(
                    overlay,
                    geo,
                    route_start,
                    (entry_place[1], entry_place[2]),
                    COL["route_a"],
                    COL["amber"],
                    pulse=pending is not None or not connected.connected,
                    priority=5,
                )
                self._draw_route(
                    overlay,
                    geo,
                    (entry_place[1], entry_place[2]),
                    route_end,
                    COL["amber"],
                    COL["violet"],
                    pulse=pending is not None or not connected.connected,
                    priority=5,
                )
            else:
                self._draw_route(
                    overlay,
                    geo,
                    route_start,
                    route_end,
                    COL["route_a"],
                    route_color_end,
                    dim=not connected.connected and pending is None,
                    pulse=True,
                    priority=5,
                )

        # City constellation for the selected country (only when zoomed in).
        if selected is not None and geo.span < 380:
            for city in selected.cities.values():
                if not geo.in_view(city.lat, city.lon, margin=4):
                    continue
                px, py = geo.project(city.lat, city.lon)
                is_current = app.selected_city_name == city.name
                self._paint_dot(
                    overlay,
                    geo,
                    round(px),
                    round(py),
                    COL["cyan"] if is_current else "#155e75",
                    4 if not is_current else 12,
                )
                if is_current:
                    self._paint_ring(
                        overlay, geo, px, py, 3.0, COL["cyan"], 12, 1.0
                    )

        # Country markers, excluded ones below available ones.
        excluded = set(app.excluded_codes)
        for country in app.country_list:
            if not geo.in_view(country.lat, country.lon, margin=10):
                continue
            px, py = geo.project(country.lat, country.lon)
            if country.code in excluded:
                self._paint_disk(overlay, geo, px, py, 1.1, COL["excluded"], 6)
        for country in app.country_list:
            if country.code in excluded:
                continue
            if not geo.in_view(country.lat, country.lon, margin=10):
                continue
            px, py = geo.project(country.lat, country.lon)
            if country.servers:
                radius = 1.0 + min(1.7, math.log10(country.servers + 1) * 0.45)
            else:
                radius = 1.15
            if geo.span < 400:
                radius += 0.6
            if self._hover_code == country.code:
                self._paint_disk(overlay, geo, px, py, radius + 1.2, COL["purple_hi"], 8)
            self._paint_disk(overlay, geo, px, py, radius, COL["purple"], 7)

        # Source marker.
        if geo.in_view(home.lat, home.lon, margin=8):
            px, py = geo.project(home.lat, home.lon)
            self._paint_disk(overlay, geo, px, py, 1.6, COL["cyan"], 10)
            self._paint_ring(overlay, geo, px, py, 3.2, COL["cyan_dim"], 9, 0.8)
            labels.append((f" ◉ {home.label} ", home.lat, home.lon, "#d6fbff", "#0e4b57"))

        # Selected / destination marker and ring.
        if selected is not None and geo.in_view(selected.lat, selected.lon, margin=8):
            px, py = geo.project(selected.lat, selected.lon)
            pulse = 0.5 + 0.5 * math.sin(self._phase * 3.0)
            self._paint_disk(overlay, geo, px, py, 2.0, COL["violet"], 10)
            self._paint_ring(
                overlay,
                geo,
                px,
                py,
                3.6 + pulse * 1.8,
                COL["purple_hi"],
                9,
                0.9,
            )
            if geo.span < 400:
                self._paint_ring(overlay, geo, px, py, 6.0 + pulse * 2.0, COL["purple"], 8, 0.7)
            if not connected.connected and pending is None:
                short_name = selected.name if len(selected.name) <= 16 else selected.code
                labels.append(
                    (f" ◆ {short_name} ", selected.lat, selected.lon, "#ffffff", "#3b2c82")
                )

        if connected.connected and connected.country_code:
            dest = app.countries.get(connected.country_code)
            if dest and geo.in_view(dest.lat, dest.lon, margin=8):
                px, py = geo.project(dest.lat, dest.lon)
                pulse = 0.5 + 0.5 * math.sin(self._phase * 3.0)
                self._paint_disk(overlay, geo, px, py, 2.2, COL["green_hi"], 12)
                self._paint_ring(overlay, geo, px, py, 4.0 + pulse * 1.8, COL["green"], 11, 0.9)
                label = connected.server_name or dest.code
                if connected.city:
                    label = f"{label} · {connected.city}"
                if len(label) > 20:
                    label = label[:20]
                labels.append(
                    (f" {label} ", dest.lat, dest.lon, "#eafff4", "#14532d")
                )
            if entry_place and geo.in_view(entry_place[1], entry_place[2], margin=8):
                labels.append(
                    (
                        f" via {entry_place[0]} ",
                        entry_place[1],
                        entry_place[2],
                        "#fff7ed",
                        "#78350f",
                    )
                )
            if route_label:
                # Give the destination label priority over the generic route text.
                pass

        if pending is not None and pending.get("label"):
            lat, lon = pending.get("lat"), pending.get("lon")
            if lat is not None and lon is not None and geo.in_view(float(lat), float(lon), margin=8):
                pending_label = str(pending["label"])[:20]
                labels.append(
                    (
                        f" → {pending_label} ",
                        float(lat),
                        float(lon),
                        "#fff7ed",
                        "#78350f",
                    )
                )

        self._draw_labels(overlay, geo, labels)

        # Assemble runs of styled braille / overlay text.
        base_masks = self._base_masks
        base_colors = self._base_colors
        result = Text(no_wrap=True, overflow="crop")
        for cy in range(height):
            if cy:
                result.append("\n")
            current_style: Optional[Style] = None
            run: list[str] = []
            for cx in range(width):
                index = cy * width + cx
                paint = overlay.get(index)
                if paint is not None:
                    if paint.char is not None:
                        glyph = paint.char
                    else:
                        glyph = chr(0x2800 + paint.mask) if paint.mask else " "
                    style = self._style(paint.fg, paint.bg, paint.bold)
                else:
                    mask = base_masks[index] if index < len(base_masks) else 0
                    color = base_colors[index] if index < len(base_colors) else None
                    if not mask or color is None:
                        glyph = " "
                        style = None
                    else:
                        glyph = chr(0x2800 + mask)
                        style = self._style(color)
                if style != current_style:
                    if run:
                        result.append("".join(run), style=current_style)
                        run = []
                    current_style = style
                run.append(glyph)
            if run:
                result.append("".join(run), style=current_style)
        return result

    # ------------------------------------------------------------- interaction

    def _marker_at(self, cell_x: int, cell_y: int) -> Optional["Country"]:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        geo = self._ensure_geo()
        best: Optional[Country] = None
        best_distance = 1e9
        threshold = 4.5 + (1.0 - min(1.0, geo.span / WORLD_W)) * 2.5
        for country in app.country_list:
            if not geo.in_view(country.lat, country.lon, margin=10):
                continue
            px, py = geo.project(country.lat, country.lon)
            cx, cy = px / 2, py / 4
            # Compare against the centre of the clicked cell rather than its
            # top-left corner; otherwise north-west neighbours win ties.
            distance = math.hypot(cx - (cell_x + 0.5), cy - (cell_y + 0.5))
            if distance < best_distance and distance <= threshold:
                best = country
                best_distance = distance
        return best

    def on_click(self, event: events.Click) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        country = self._marker_at(event.x, event.y)
        if country is None:
            return
        event.stop()
        app.select_country(country.code)
        self.ensure_visible(country.code)
        if event.chain >= 2:
            app.main_screen.request_connect()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        country = self._marker_at(event.x, event.y)
        code = country.code if country else None
        if code == self._hover_code:
            return
        self._hover_code = code
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if country is not None:
            text = f"⌖ {country.name} · {country.code}"
            if country.servers:
                text = f"⌖ {country.name} · {fmt_compact(country.servers)} srv · {country.load}%"
            app.update_map_meta(text)
        else:
            app.update_map_meta(None)
        self.refresh()

    def _on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self.zoom_at(0.80, event.x * 2, event.y * 4)

    def _on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self.zoom_at(1.25, event.x * 2, event.y * 4)

    def zoom_at(self, factor: float, px: float, py: float) -> None:
        geo = self._ensure_geo()
        old_span = geo.span
        new_span = max(80.0, min(1100.0, old_span * factor))
        if new_span == old_span:
            return
        wx = geo.x0 + (px / geo.px_width) * old_span
        wy = geo.y0 + (py / geo.px_height) * geo.span_y
        new_span_y = new_span * (geo.px_height / geo.px_width)
        self.view_span = new_span
        self.view_center_x = wx + (px / geo.px_width) * new_span - new_span / 2
        self.view_center_y = wy + (py / geo.px_height) * new_span_y - new_span_y / 2
        preview = make_geometry(
            geo.width, geo.height, self.view_center_x, self.view_center_y, new_span
        )
        self.view_center_x = preview.center_x
        self.view_center_y = preview.center_y
        self._base_key = None
        self.refresh()

    def zoom_selected(self, factor: float) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        country = app.selected_country()
        geo = self._ensure_geo()
        if country is None:
            self.zoom_at(factor, geo.px_width / 2, geo.px_height / 2)
            return
        wx, wy = robinson_forward(country.lat, country.lon)
        new_span = max(80.0, min(1100.0, geo.span * factor))
        new_span_y = new_span * (geo.px_height / geo.px_width)
        self.view_span = new_span
        self.view_center_x = wx
        self.view_center_y = wy
        preview = make_geometry(
            geo.width, geo.height, self.view_center_x, self.view_center_y, new_span
        )
        self.view_center_x = preview.center_x
        self.view_center_y = preview.center_y
        self._base_key = None
        self.refresh()

    def reset_view(self) -> None:
        self.view_span = WORLD_W
        self.view_center_x = WORLD_W / 2
        self.view_center_y = WORLD_H / 2
        self._base_key = None
        self.refresh()

    def ensure_visible(self, code: str) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        country = app.countries.get(code)
        if country is None:
            return
        geo = self._ensure_geo()
        if geo.span >= 950:
            return
        px, py = geo.project(country.lat, country.lon)
        if 0.08 * geo.px_width <= px <= 0.92 * geo.px_width and 0.08 * geo.px_height <= py <= 0.92 * geo.px_height:
            return
        wx, wy = robinson_forward(country.lat, country.lon)
        self.view_center_x = wx
        self.view_center_y = wy
        preview = make_geometry(geo.width, geo.height, wx, wy, geo.span)
        self.view_center_x = preview.center_x
        self.view_center_y = preview.center_y
        self._base_key = None
        self.refresh()

    def move_selection(self, direction: str) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        geo = self._ensure_geo()
        current = app.selected_country()
        if current is None:
            country = app.country_list[0] if app.country_list else None
            if country:
                app.select_country(country.code)
                self.ensure_visible(country.code)
            return
        cp = geo.project(current.lat, current.lon)
        cx, cy = cp[0] / 2, cp[1] / 4
        best: Optional[Country] = None
        best_score = 1e18
        for country in app.country_list:
            if country.code == current.code:
                continue
            px, py = geo.project(country.lat, country.lon)
            x, y = px / 2, py / 4
            dx, dy = x - cx, y - cy
            if direction == "right":
                proj, perp = dx, abs(dy)
            elif direction == "left":
                proj, perp = -dx, abs(dy)
            elif direction == "up":
                proj, perp = -dy, abs(dx)
            else:
                proj, perp = dy, abs(dx)
            if proj <= 0.4:
                continue
            score = perp * 2.8 + proj * 0.18
            if score < best_score:
                best_score = score
                best = country
        if best is not None:
            app.select_country(best.code)
            self.ensure_visible(best.code)

    def hover_country(self) -> Optional["Country"]:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if self._hover_code:
            return app.countries.get(self._hover_code)
        return None


# ===========================================================================
# Main screen
# ===========================================================================


class MainScreen(Screen):
    """The map, status deck, feature toggles and primary controls."""

    BINDINGS = [
        Binding("up", "nav_up", "Select up", show=False),
        Binding("down", "nav_down", "Select down", show=False),
        Binding("left", "nav_left", "Select left", show=False),
        Binding("right", "nav_right", "Select right", show=False),
        Binding("enter", "connect_selected", "Connect selected", show=False),
        Binding("d", "disconnect", "Disconnect", show=False),
        Binding("c", "quick_connect", "Quick connect", show=False),
        Binding("f", "find", "Find region", show=False),
        Binding("x", "cities", "Cities", show=False),
        Binding("a", "autoconnect", "AutoConnect", show=False),
        Binding("e", "exclusions", "AutoConnect exclusions", show=False),
        Binding("s", "settings", "Settings", show=False),
        Binding("i", "account", "Account", show=False),
        Binding("l", "activity", "Activity log", show=False),
        Binding("v", "server_id", "Server ID", show=False),
        Binding("question_mark", "help", "Help", show=False),
        Binding("p", "toggle_p2p", "Toggle P2P", show=False),
        Binding("u", "toggle_securecore", "Toggle Secure Core", show=False),
        Binding("t", "toggle_tor", "Toggle Tor", show=False),
        Binding("r", "toggle_random", "Toggle random", show=False),
        Binding("plus", "zoom_in", "Zoom in", show=False),
        Binding("equals_sign", "zoom_in", "Zoom in", show=False),
        Binding("minus", "zoom_out", "Zoom out", show=False),
        Binding("0", "reset_view", "World view", show=False),
        Binding("escape", "clear_selection", "Clear city / reset", show=False),
        Binding("q", "quit_app", "Quit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.map: Optional[MapView] = None
        self.primary: Optional[BigAction] = None
        self.footer_status: Optional[Static] = None
        self.footer_keys: Optional[Static] = None
        self.map_meta: Optional[Static] = None
        self._pills: dict[str, Pill] = {}
        self._footer_message = "Starting Proton Orbit…"
        self._footer_kind = "info"
        self._last_sync = 0.0
        self._map_meta_hover: Optional[str] = None
        self._poll_started = False
        self._boot_done = False

    # ---------------------------------------------------------------- compose

    def compose(self) -> ComposeResult:
        with Vertical(id="main"):
            with Horizontal(id="header"):
                yield Static(
                    "[#8b5cf6]◢◤[/]  [#f4f1ff]PROTON[/] [#a78bfa]ORBIT[/]",
                    id="logo",
                )
                yield Static("· VPN CONTROL DECK", id="tagline")
                yield Static("", id="header-spacer")
                yield Static("", id="status-pill")
                yield Static("", id="account-label")
            with Horizontal(id="body"):
                with Vertical(id="left"):
                    with Vertical(id="map-panel"):
                        with Horizontal(id="map-head"):
                            yield Static("◇ WORLD NETWORK", id="map-title")
                            yield Static("", id="map-meta")
                            with Horizontal(id="zoom-box"):
                                yield Button("−", id="zoom-out", classes="mapctl")
                                yield Button("+", id="zoom-in", classes="mapctl")
                                yield Button("WORLD", id="zoom-reset", classes="mapctl")
                        yield MapView(id="map")
                        yield Static(
                            "[#8b5cf6]●[/] region   [#c4b5fd]◆[/] selected   "
                            "[#22d3ee]◉[/] you   [#7e3048]●[/] excluded   "
                            "[#59618a]─ route[/]",
                            id="map-legend",
                        )
                    with Horizontal(id="actions"):
                        for key, label in (
                            ("p2p", "P2P"),
                            ("securecore", "SECURE"),
                            ("tor", "TOR"),
                            ("random", "RANDOM"),
                        ):
                            pill = Pill(key, label, classes="pill")
                            self._pills[key] = pill
                            yield pill
                        yield Static("", id="actions-spacer")
                        yield Button("⚡ QUICK", id="quick")
                        yield BigAction("CONNECT", id="primary")
                with Vertical(id="side"):
                    with VerticalScroll(id="side-scroll"):
                        yield Static("", id="connection-card", classes="card")
                        yield Static("", id="region-card", classes="card")
                        yield Static("", id="route-card", classes="card")
                        yield Static("", id="auto-card", classes="card")
                    yield Button(
                        "⊘ AUTOCONNECT EXCLUSIONS",
                        id="exclude-btn",
                    )
                    with Grid(id="nav"):
                        yield Button("⌕  FIND REGION", id="nav-find", classes="navbtn")
                        yield Button("◫  CITIES", id="nav-cities", classes="navbtn")
                        yield Button("⌗  SERVER ID", id="nav-server", classes="navbtn")
                        yield Button("⟳  AUTOCONNECT", id="nav-auto", classes="navbtn")
                        yield Button("⚙  SETTINGS", id="nav-settings", classes="navbtn")
                        yield Button("◇  ACCOUNT", id="nav-account", classes="navbtn")
                        yield Button("≡  ACTIVITY", id="nav-activity", classes="navbtn")
                        yield Button("?  HELP", id="nav-help", classes="navbtn")
            with Vertical(id="footer"):
                yield Static("", id="footer-keys")
                yield Static("", id="footer-status")

    def on_mount(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.main_screen = self
        self.map = self.query_one("#map", MapView)
        self.primary = self.query_one("#primary", BigAction)
        self.footer_status = self.query_one("#footer-status", Static)
        self.footer_keys = self.query_one("#footer-keys", Static)
        self.map_meta = self.query_one("#map-meta", Static)
        self._apply_responsive()
        self.refresh_all()
        self.set_interval(1.0, self._tick_ui)
        self.run_worker(self._boot(), group="boot")
        self.map.focus()

    def on_resize(self, event: events.Resize) -> None:
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        width = self.app.size.width
        main = self.query_one("#main", Vertical)
        main.set_class(width < 108, "compact")
        main.set_class(width < 84, "narrow")
        self.refresh_footer()

    # ------------------------------------------------------------------- boot

    async def _boot(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        self.set_status("Syncing local network index…", "info")
        try:
            await app.ensure_server_index()
        except Exception as exc:
            app.record_error("server index", exc)
        self.refresh_all()

        if not CLI_BIN:
            self.set_status(
                "protonvpn CLI not found in PATH. Set PROTONVPN_BIN and restart.",
                "error",
            )
        else:
            self.set_status("Reading VPN state…", "info")
            try:
                await app.refresh_status(record=False)
                await app.refresh_account()
            except Exception as exc:
                app.record_error("initial status", exc)
            self.refresh_all()

            self.set_status("Refreshing region catalogue via protonvpn countries…", "info")
            try:
                await app.load_countries_from_cli()
            except Exception as exc:
                app.record_error("countries", exc)
            self.refresh_all()

        app.ensure_initial_selection()
        self._last_sync = time.monotonic()
        self._boot_done = True
        self.set_status(
            "Link ready. Arrows select · Enter connects · mouse works everywhere.",
            "ok",
        )
        self.refresh_all()
        if not self._poll_started:
            self.set_interval(4.0, self._poll_status)
            self._poll_started = True

        if app.config["autoconnect"].get("enabled") and not app.connection.connected:
            if app.signed_in is not False:
                await asyncio.sleep(1.2)
                if not app.busy and not app.connection.connected:
                    self.start_autoconnect(launch=True)

    def _tick_ui(self) -> None:
        if self.app.busy:
            frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            index = int(time.monotonic() * 10) % len(frames)
            self.set_status(f"{frames[index]} {self.app.busy_message}", "busy", redraw=False)
        self.refresh_connection_card()
        self.refresh_footer()

    async def _poll_status(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy or not CLI_BIN:
            return
        self.run_worker(self._poll_once(), group="status-poll", exclusive=True)

    async def _poll_once(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy:
            return
        try:
            changed = await app.refresh_status(record=False)
            self._last_sync = time.monotonic()
            if changed:
                self.refresh_all()
        except Exception as exc:
            app.record_error("status poll", exc, quiet=True)

    # --------------------------------------------------------------- rendering

    def set_status(self, message: str, kind: str = "info", redraw: bool = True) -> None:
        self._footer_message = message
        self._footer_kind = kind
        if redraw:
            self.refresh_footer()
            if self.footer_status is not None:
                self.footer_status.set_class(kind == "error", "error")
                self.footer_status.set_class(kind in ("busy", "info"), "busy")

    def refresh_all(self) -> None:
        self.refresh_header()
        self.refresh_cards()
        self.refresh_actions()
        self.refresh_map_head()
        self.refresh_footer()
        if self.map is not None:
            self.map.refresh()

    def refresh_header(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        pill = self.query_one("#status-pill", Static)
        cls, text = status_bits(app)
        for name in ("connected", "disconnected", "busy"):
            pill.set_class(name == cls, name)
        pill.update(text)
        account = self.query_one("#account-label", Static)
        if app.signed_in:
            account.update(f"◇ {app.account_name or 'SIGNED IN'}")
        elif app.signed_in is False:
            account.update("◇ SIGN IN REQUIRED")
        else:
            account.update("◇ SYNCING ACCOUNT…")

    def refresh_connection_card(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        card = self.query_one("#connection-card", Static)
        if app.busy:
            target = ""
            if app.pending:
                target = markup(str(app.pending.get("label") or ""))
            body = (
                f"[bold {COL['muted']}]CONNECTION[/]\n"
                f"[bold {COL['amber']}]◌ {markup(app.busy_message.upper())}[/]\n"
                + (f"[{COL['text_dim']}]{target}[/]\n" if target else "")
                + f"[{COL['muted']}]The protonvpn CLI is working…[/]"
            )
            card.update(body)
            return
        if app.connection.connected:
            conn = app.connection
            duration = fmt_duration(time.time() - conn.since) if conn.since else "—"
            location = markup(conn.location or conn.country_name or "—")
            server = markup(conn.server_name or "VPN")
            protocol = markup((conn.protocol or "—").upper())
            load_color = COL["green"] if conn.load < 50 else (COL["amber"] if conn.load < 80 else COL["red"])
            ip_line = (
                f"\n[{COL['muted']}]new IP[/]  [{COL['text']}]{markup(conn.ip)}[/]"
                if conn.ip
                else ""
            )
            card.update(
                f"[bold {COL['muted']}]CONNECTION[/]  [{COL['muted']}]{duration}[/]\n"
                f"[bold {COL['green_hi']}]● CONNECTED[/]\n"
                f"[bold {COL['text']}]{server}[/]  [{COL['text_dim']}]{location}[/]\n"
                f"[{COL['muted']}]load[/] [{load_color}]{conn.load}%[/]  "
                f"[{COL['muted']}]·[/]  [{COL['purple_hi']}]{protocol}[/]"
                f"{ip_line}"
            )
            return
        auto = "armed" if app.config["autoconnect"].get("enabled") else "off"
        card.update(
            f"[bold {COL['muted']}]CONNECTION[/]\n"
            f"[bold {COL['text_dim']}]○ STANDBY[/]\n"
            f"[{COL['text_dim']}]No active tunnel.[/]\n"
            f"[{COL['muted']}]Select a region and press ENTER.[/]\n"
            f"[{COL['faint']}]AutoConnect {auto} · {len(app.excluded_codes)} excluded[/]"
        )

    def refresh_cards(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        self.refresh_connection_card()
        selected = app.selected_country()
        region = self.query_one("#region-card", Static)
        if selected is None:
            region.update(
                f"[bold {COL['muted']}]SELECTED REGION[/]\n"
                f"[{COL['text_dim']}]Nothing selected.[/]\n"
                f"[{COL['muted']}]Click a marker or use the arrow keys.[/]"
            )
        else:
            city_count = len(selected.cities) if selected.cities else 0
            stat_line = (
                f"{fmt_int(selected.servers)} servers · {selected.load}% load"
                if selected.servers
                else "region data not cached"
            )
            feature_line = f"{city_count} cities · {selected.feature_line}" if city_count else selected.feature_line
            city_line = ""
            if app.selected_city_name:
                city = selected.cities.get(app.selected_city_name)
                load = f" · {city.load}%" if city and city.load else ""
                city_line = (
                    f"\n[{COL['cyan']}]◆ {markup(app.selected_city_name)}{load}[/]"
                    f"  [{COL['faint']}]ESC clears[/]"
                )
            excluded = selected.code in app.excluded_codes
            badge = (
                f"\n[{COL['red']}]⛔ EXCLUDED FROM AUTOCONNECT[/]"
                if excluded
                else f"\n[{COL['green']}]✓ ALLOWED FOR AUTOCONNECT[/]"
            )
            region.update(
                f"[bold {COL['muted']}]SELECTED REGION[/]\n"
                f"[bold {COL['text']}]{markup(selected.name)}[/]  "
                f"[{COL['purple_hi']}]{selected.code}[/]\n"
                f"[{COL['text_dim']}]{stat_line}[/]\n"
                f"[{COL['muted']}]{markup(feature_line)}[/]"
                f"{city_line}{badge}"
            )

        route = self.query_one("#route-card", Static)
        if app.connection.connected:
            conn = app.connection
            dest_label = markup(conn.city or conn.country_name or conn.server_name)
            dest_code = markup(conn.country_code or "")
            if conn.entry_code and conn.entry_code != conn.country_code:
                entry_country = app.countries.get(conn.entry_code)
                entry_name = conn.entry_country or conn.entry_code
                leg1 = 0.0
                leg2 = 0.0
                if entry_country:
                    leg1 = haversine_km(app.home.lat, app.home.lon, entry_country.lat, entry_country.lon)
                    dest_country = app.countries.get(conn.country_code)
                    if dest_country:
                        dest_city = dest_country.cities.get(conn.city)
                        dlat = dest_city.lat if dest_city else dest_country.lat
                        dlon = dest_city.lon if dest_city else dest_country.lon
                        leg2 = haversine_km(entry_country.lat, entry_country.lon, dlat, dlon)
                route.update(
                    f"[bold {COL['muted']}]ROUTE[/]  [{COL['green']}]LIVE[/]\n"
                    f"[{COL['cyan']}]◉[/] YOU  [{COL['text_dim']}]{markup(app.home.label)}[/]\n"
                    f"  [{COL['faint']}]│[/]  {fmt_distance(leg1)}\n"
                    f"[{COL['amber']}]◇[/] via  [{COL['text']}]{markup(entry_name)}[/]\n"
                    f"  [{COL['faint']}]│[/]  {fmt_distance(leg2)}\n"
                    f"[{COL['green_hi']}]◆[/] {dest_label}  [{COL['text_dim']}]{dest_code}[/]\n"
                    f"[{COL['faint']}]secure core · encrypted[/]"
                )
            else:
                dest_country = app.countries.get(conn.country_code)
                distance = 0.0
                if dest_country:
                    dest_city = dest_country.cities.get(conn.city)
                    dlat = dest_city.lat if dest_city else dest_country.lat
                    dlon = dest_city.lon if dest_city else dest_country.lon
                    distance = haversine_km(app.home.lat, app.home.lon, dlat, dlon)
                route.update(
                    f"[bold {COL['muted']}]ROUTE[/]  [{COL['green']}]LIVE[/]\n"
                    f"[{COL['cyan']}]◉[/] YOU  [{COL['text_dim']}]{markup(app.home.label)}[/]\n"
                    f"  [{COL['faint']}]│[/]  {fmt_distance(distance)} · encrypted\n"
                    f"  [{COL['faint']}]╰────────────▶[/]\n"
                    f"[{COL['green_hi']}]◆[/] {dest_label}  [{COL['text_dim']}]{dest_code}[/]\n"
                    f"[{COL['faint']}]{markup((conn.protocol or 'vpn').upper())} tunnel[/]"
                )
        else:
            target = app.pending_target_place() if app.busy else app.selection_place()
            if target is None:
                route.update(
                    f"[bold {COL['muted']}]ROUTE[/]\n"
                    f"[{COL['text_dim']}]No destination selected.[/]\n"
                    f"[{COL['muted']}]The route preview follows your selection.[/]"
                )
            else:
                distance = haversine_km(app.home.lat, app.home.lon, target["lat"], target["lon"])
                total = f"{fmt_distance(distance)} · encrypted"
                head = "NEGOTIATING" if app.busy else "PREVIEW"
                color = COL["amber"] if app.busy else COL["purple_hi"]
                route.update(
                    f"[bold {COL['muted']}]ROUTE[/]  [{color}]{head}[/]\n"
                    f"[{COL['cyan']}]◉[/] YOU  [{COL['text_dim']}]{markup(app.home.label)}[/]\n"
                    f"  [{COL['faint']}]│[/]  {total}\n"
                    f"  [{COL['faint']}]╰────────────▶[/]\n"
                    f"[{color}]◆[/] {markup(target['label'])}  "
                    f"[{COL['text_dim']}]{markup(target['code'])}[/]"
                )

        auto = self.query_one("#auto-card", Static)
        excluded = len(app.excluded_codes)
        enabled = bool(app.config["autoconnect"].get("enabled"))
        preferred = app.config["autoconnect"].get("preferred") or ""
        preferred_name = ""
        if preferred and preferred in app.countries:
            preferred_name = app.countries[preferred].name
        auto.update(
            f"[bold {COL['muted']}]AUTOCONNECT[/]\n"
            f"[bold {COL['green_hi'] if enabled else COL['text_dim']}]{'◉ ON' if enabled else '○ OFF'}[/]  "
            f"[{COL['text_dim']}]excluded[/] [{COL['red'] if excluded else COL['text_dim']}]{excluded}[/]\n"
            f"[{COL['muted']}]{'preferred: ' + markup(preferred_name) if preferred_name else 'weighted random region'}[/]\n"
            f"[{COL['faint']}]Manual connects ignore exclusions.[/]"
        )

        btn = self.query_one("#exclude-btn", Button)
        if selected is None:
            btn.label = f"⊘ AUTOCONNECT EXCLUSIONS · {excluded}"
            btn.set_class(False, "excluded")
        elif selected.code in app.excluded_codes:
            btn.label = f"✓ ALLOW {selected.code} IN AUTO"
            btn.set_class(True, "excluded")
        else:
            btn.label = f"⊘ EXCLUDE {selected.code} FROM AUTO"
            btn.set_class(False, "excluded")

    def refresh_actions(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        for key, pill in self._pills.items():
            pill.set_active(bool(app.features.get(key)))
        primary = self.primary
        if primary is None:
            return
        primary.set_class(False, "danger")
        primary.set_class(False, "busy")
        if app.busy:
            primary.set_label("WORKING…")
            primary.set_class(True, "busy")
            primary.set_class(False, "danger")
        elif app.connection.connected:
            primary.set_label("DISCONNECT")
            primary.set_class(False, "busy")
            primary.set_class(True, "danger")
        else:
            primary.set_label("CONNECT")
            primary.set_class(False, "busy")
            primary.set_class(False, "danger")

    def refresh_map_head(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if self.map_meta is None:
            return
        if self._map_meta_hover:
            self.map_meta.update(self._map_meta_hover)
            return
        geo_span = self.map.view_span if self.map else WORLD_W
        zoom = max(100, round(WORLD_W / max(1.0, geo_span) * 100))
        total = sum(c.servers for c in app.country_list)
        if total:
            stats = f"{len(app.country_list)} REGIONS · {fmt_compact(total)}"
        else:
            stats = f"{len(app.country_list)} REGIONS"
        view = "WORLD" if geo_span >= 950 else f"{zoom}%"
        self.map_meta.update(f"{view} · {stats}")

    def update_map_meta(self, text: Optional[str]) -> None:
        self._map_meta_hover = text
        self.refresh_map_head()
        if self.map is not None:
            self.map.refresh()

    def refresh_footer(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if self.footer_keys is None or self.footer_status is None:
            return
        width = self.app.size.width
        if width < 90:
            keys = (
                f"[{COL['purple_hi']}]↑↓←→[/] select · "
                f"[{COL['purple_hi']}]⏎[/] connect · "
                f"[{COL['purple_hi']}]C[/] quick · "
                f"[{COL['purple_hi']}]A[/] auto · "
                f"[{COL['purple_hi']}]S[/] settings · "
                f"[{COL['purple_hi']}]?[/] help"
            )
        elif width < 142:
            keys = (
                f"[{COL['purple_hi']}]↑↓←→[/] select · "
                f"[{COL['purple_hi']}]ENTER[/] connect · "
                f"[{COL['purple_hi']}]C[/] quick · "
                f"[{COL['purple_hi']}]D[/] disconnect · "
                f"[{COL['purple_hi']}]F[/] find · "
                f"[{COL['purple_hi']}]A[/] auto · "
                f"[{COL['purple_hi']}]S[/] settings · "
                f"[{COL['purple_hi']}]?[/] help"
            )
        else:
            keys = (
                f"[{COL['purple_hi']}]↑↓←→[/] select · "
                f"[{COL['purple_hi']}]ENTER[/] connect · "
                f"[{COL['purple_hi']}]C[/] quick · "
                f"[{COL['purple_hi']}]D[/] disconnect · "
                f"[{COL['purple_hi']}]F[/] find · "
                f"[{COL['purple_hi']}]X[/] cities · "
                f"[{COL['purple_hi']}]A[/] autoconnect · "
                f"[{COL['purple_hi']}]S[/] settings · "
                f"[{COL['purple_hi']}]L[/] activity · "
                f"[{COL['purple_hi']}]?[/] help · "
                f"[{COL['purple_hi']}]Q[/] quit"
            )
        self.footer_keys.update(keys)
        message = self._footer_message
        if not app.busy and app.connection.connected:
            suffix = f"  ·  session {fmt_duration(time.time() - app.connection.since)}"
        elif app.signed_in is False:
            suffix = "  ·  run sign-in from ACCOUNT"
        else:
            suffix = ""
        dot_color = {
            "error": COL["red"],
            "busy": COL["amber"],
            "ok": COL["green"],
            "info": COL["cyan"],
        }.get(self._footer_kind, COL["muted"])
        self.footer_status.update(
            f"[{dot_color}]●[/] [{COL['text_dim']}]{markup(message)}{suffix}[/]"
        )
        self.footer_status.set_class(self._footer_kind == "error", "error")
        self.footer_status.set_class(self._footer_kind in ("busy", "info"), "busy")

    # ----------------------------------------------------------------- actions

    def action_nav_up(self) -> None:
        if self.map:
            self.map.move_selection("up")

    def action_nav_down(self) -> None:
        if self.map:
            self.map.move_selection("down")

    def action_nav_left(self) -> None:
        if self.map:
            self.map.move_selection("left")

    def action_nav_right(self) -> None:
        if self.map:
            self.map.move_selection("right")

    def action_connect_selected(self) -> None:
        self.request_connect()

    def action_primary(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy:
            return
        if app.connection.connected:
            self.action_disconnect()
        else:
            self.request_connect()

    def action_quick_connect(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy:
            return
        flags = app.feature_flags()
        args = ["connect", *flags]
        self.start_connect(args, target=None, scan=True)

    def action_disconnect(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy:
            return
        if not app.connection.connected:
            self.notify("No active VPN connection.", severity="information")
            return
        self.run_worker(self._disconnect_flow(), group="op", exclusive=True)

    def action_find(self) -> None:
        self.app.push_screen(SearchScreen())

    def action_cities(self) -> None:
        self.open_cities()

    def action_autoconnect(self) -> None:
        self.app.push_screen(AutoconnectScreen())

    def action_exclusions(self) -> None:
        self.app.push_screen(AutoconnectScreen(focus_exclusions=True))

    def action_settings(self) -> None:
        self.open_settings()

    def action_account(self) -> None:
        self.app.push_screen(AccountScreen())

    def action_activity(self) -> None:
        self.app.push_screen(ActivityScreen())

    def action_server_id(self) -> None:
        self.app.push_screen(ServerIDScreen())

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_toggle_p2p(self) -> None:
        self._toggle_feature("p2p")

    def action_toggle_securecore(self) -> None:
        self._toggle_feature("securecore")

    def action_toggle_tor(self) -> None:
        self._toggle_feature("tor")

    def action_toggle_random(self) -> None:
        self._toggle_feature("random")

    def _toggle_feature(self, key: str) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.features[key] = not bool(app.features.get(key))
        app.save_preferences()
        self.refresh_actions()
        self.refresh_cards()
        if self.map:
            self.map.refresh()
        state = "on" if app.features[key] else "off"
        self.notify(f"{key.upper()} {state}", timeout=1.5)

    def action_zoom_in(self) -> None:
        if self.map:
            self.map.zoom_selected(0.75)
            self.refresh_map_head()

    def action_zoom_out(self) -> None:
        if self.map:
            self.map.zoom_selected(1.35)
            self.refresh_map_head()

    def action_reset_view(self) -> None:
        if self.map:
            self.map.reset_view()
            self.refresh_map_head()

    def action_clear_selection(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.selected_city_name:
            app.selected_city_name = None
            self.set_status("City cleared; the whole region is selected.", "info")
            self.refresh_all()
            return
        if self.map and self.map.view_span < 950:
            self.map.reset_view()
            self.refresh_map_head()
            return

    def action_quit_app(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy:
            self.notify("A CLI operation is still running. Try again in a moment.", severity="warning")
            return
        app.exit()

    # ------------------------------------------------------------ button events

    @on(BigAction.Pressed)
    def _primary_pressed(self, event: BigAction.Pressed) -> None:
        event.stop()
        if event.action.id == "primary":
            self.action_primary()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "quick":
            self.action_quick_connect()
        elif button_id == "zoom-out":
            self.action_zoom_out()
        elif button_id == "zoom-in":
            self.action_zoom_in()
        elif button_id == "zoom-reset":
            self.action_reset_view()
        elif button_id == "exclude-btn":
            selected = self.app.selected_country()  # type: ignore[attr-defined]
            if selected is None:
                self.action_autoconnect()
            else:
                self.toggle_selected_exclusion()
        elif button_id == "nav-find":
            self.action_find()
        elif button_id == "nav-cities":
            self.action_cities()
        elif button_id == "nav-server":
            self.app.push_screen(ServerIDScreen())
        elif button_id == "nav-auto":
            self.action_autoconnect()
        elif button_id == "nav-settings":
            self.action_settings()
        elif button_id == "nav-account":
            self.action_account()
        elif button_id == "nav-activity":
            self.action_activity()
        elif button_id == "nav-help":
            self.action_help()
        else:
            return
        event.stop()

    def on_pill_changed(self, message: Pill.Changed) -> None:
        message.stop()
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.features[message.pill.key] = message.active
        app.save_preferences()
        self.refresh_actions()
        self.refresh_cards()
        if self.map:
            self.map.refresh()

    # --------------------------------------------------------------- operations

    def toggle_selected_exclusion(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        country = app.selected_country()
        if country is None:
            self.action_autoconnect()
            return
        now_excluded = country.code not in app.excluded_codes
        app.set_excluded(country.code, now_excluded)
        self.refresh_all()
        if now_excluded:
            self.notify(f"{country.name} excluded from AutoConnect.", timeout=2)
        else:
            self.notify(f"{country.name} allowed for AutoConnect.", timeout=2)

    def request_connect(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy:
            return
        if app.signed_in is False:
            self.set_status("Sign in required. Open ACCOUNT to authenticate.", "error")
            self.app.push_screen(AccountScreen())
            return
        args, target = app.connect_args_for_selection()
        self.start_connect(args, target=target)

    def start_connect(
        self,
        args: list[str],
        target: Optional[dict[str, Any]],
        *,
        scan: bool = False,
        launch: bool = False,
    ) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy:
            return
        self.run_worker(
            self._connect_flow(args, target, scan=scan, launch=launch),
            group="op",
            exclusive=True,
        )

    async def _connect_flow(
        self,
        args: list[str],
        target: Optional[dict[str, Any]],
        *,
        scan: bool = False,
        launch: bool = False,
    ) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.busy = True
        app.busy_message = "Connecting…" if not scan else "Scanning global network…"
        if scan:
            app.pending = {"scan": True, "label": "global fastest"}
        else:
            app.pending = target
        self.refresh_all()
        started = time.monotonic()
        res = await app.cli.run(*args, timeout=125)
        app.busy = False
        app.busy_message = ""
        app.pending = None
        if res.ok:
            parsed = parse_connect_output(res.text)
            try:
                await app.refresh_status(record=False)
            except Exception:
                pass
            # Set the IP after the status refresh: _apply_connected clears a
            # stale IP when the server name changes, and this is a new server.
            if parsed.get("ip"):
                app.connection.ip = parsed["ip"]
            if not app.connection.connected:
                # The CLI reported success but status could not confirm it yet.
                app.connection.connected = True
                app.connection.server_name = parsed.get("server", "")
                app.connection.location = parsed.get("location", "")
                if not app.connection.since:
                    app.connection.since = time.time()
            app.ensure_initial_selection()
            where = app.connection.location or parsed.get("location") or "the selected region"
            self.set_status(f"Connected to {where}.", "ok")
            self.notify(f"Connected · {where}", timeout=3)
            if "Port forwarding" in res.text:
                self.notify("Port forwarding is active on this server.", timeout=4)
            if launch:
                app.record_activity_event("AutoConnect", True, f"Connected to {where}.")
        else:
            detail = res.error_text
            self.set_status("Connection failed.", "error")
            if launch:
                self.notify("AutoConnect failed — see ACTIVITY for details.", severity="error", timeout=5)
                app.record_activity_event("AutoConnect", False, detail)
            else:
                self.app.push_screen(
                    MessageScreen(
                        "Connection failed",
                        detail,
                        severity="error",
                        hint="Try another region, clear feature filters, or check the CLI output.",
                    )
                )
        app.busy_message = ""
        self._last_sync = time.monotonic()
        self.refresh_all()

    async def _disconnect_flow(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.busy = True
        app.busy_message = "Disconnecting…"
        self.refresh_all()
        res = await app.cli.run("disconnect", timeout=45)
        app.busy = False
        app.busy_message = ""
        if res.ok:
            app.connection.reset()
            app.pending = None
            self.set_status("Disconnected; network restored.", "ok")
            self.notify("VPN disconnected.", timeout=2)
            try:
                await app.refresh_status(record=False)
            except Exception:
                pass
        else:
            self.set_status("Disconnect failed.", "error")
            self.app.push_screen(
                MessageScreen(
                    "Disconnect failed",
                    res.error_text,
                    severity="error",
                    hint="The CLI may still be cleaning up. Check ACTIVITY and try again.",
                )
            )
        self._last_sync = time.monotonic()
        self.refresh_all()

    def start_autoconnect(self, launch: bool = False) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy or app.connection.connected:
            return
        target = app.autoconnect_target()
        if target is None:
            self.set_status(
                "AutoConnect has no allowed region. Clear an exclusion first.",
                "error",
            )
            if not launch:
                self.app.push_screen(
                    MessageScreen(
                        "AutoConnect has no target",
                        "Every region is excluded. Open AutoConnect and allow at least one region.",
                        severity="warning",
                    )
                )
            return
        app.select_country(target.code)
        self.set_status(f"AutoConnect chose {target.name}.", "info")
        self.start_connect(
            ["connect", "--country", target.code, *app.feature_flags()],
            target=app.place_for_country(target),
            launch=launch,
        )

    # ------------------------------------------------------------ modal loaders

    def open_cities(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        country = app.selected_country()
        if country is None:
            self.set_status("Select a region first.", "info")
            self.notify("Select a region before opening cities.", timeout=2)
            return
        self.app.push_screen(CitiesScreen(country.code))

    def open_settings(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy:
            return
        self.run_worker(self._load_settings_and_open(), group="loader", exclusive=True)

    async def _load_settings_and_open(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.busy = True
        app.busy_message = "Reading CLI configuration…"
        self.refresh_all()
        res = await app.cli.run("config", "list", timeout=30)
        app.busy = False
        app.busy_message = ""
        self.refresh_all()
        if not res.ok:
            self.set_status("Could not read CLI settings.", "error")
            self.app.push_screen(
                MessageScreen(
                    "Could not read settings",
                    res.error_text,
                    severity="error",
                    hint="The CLI requires an authenticated account for config list.",
                )
            )
            return
        self.set_status("CLI settings loaded.", "ok")
        settings = parse_config_table(res.text)
        self.app.push_screen(SettingsScreen(settings))

    # --------------------------------------------------------------- sign in/out

    async def signin_interactive(self, username: str, totp: bool) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.busy:
            return
        if not CLI_BIN:
            self.app.push_screen(
                MessageScreen("CLI not found", "Install proton-vpn-cli or set PROTONVPN_BIN.", "error")
            )
            return
        cmd = [CLI_BIN, "signin", username]
        if totp:
            cmd.append("--totp")
        was_signed_in = bool(app.signed_in)
        previous_account = app.account_name
        app.busy = True
        app.busy_message = "Signing in through protonvpn CLI…"
        self.refresh_all()
        try:
            with self.app.suspend():
                print(f"\n$ {' '.join(cmd)}\n", flush=True)
                result = subprocess.run(
                    cmd, check=False, stderr=subprocess.PIPE, text=True
                )
                error_detail = clean_output(result.stderr or "")
                if error_detail:
                    print(error_detail, file=sys.stderr, flush=True)
            activity_output = f"interactive sign-in exited with code {result.returncode}"
            if error_detail:
                activity_output += f"\n{error_detail}"
            app.record_activity_event(
                " ".join(cmd[1:]),
                result.returncode == 0,
                activity_output,
            )
            # Keep the operation marked busy so no other CLI action can start,
            # but force these refreshes past the busy guard: the interactive
            # command has already finished and its result must be reflected.
            await app.refresh_account(force=True)
            await app.refresh_status(record=False, force=True)
            success, message = signin_outcome(
                result.returncode,
                app.signed_in,
                was_signed_in,
                previous_account,
                app.account_name,
                error_detail,
            )
            self.set_status(message, "ok" if success else "error")
            if success:
                self.notify("Signed in successfully.", timeout=3)
                try:
                    await app.load_countries_from_cli()
                except Exception as exc:
                    # The account is already authenticated; a catalogue
                    # refresh failure must not turn the sign-in into a
                    # misleading failure message.
                    app.record_error("post-sign-in countries", exc, quiet=True)
        except Exception as exc:
            self.set_status(f"Sign-in failed: {exc}", "error")
            app.record_error("signin", exc)
        finally:
            app.busy = False
            app.busy_message = ""
            self.refresh_all()

    async def signout_cli(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.busy = True
        app.busy_message = "Signing out…"
        self.refresh_all()
        res = await app.cli.run("signout", timeout=60)
        app.busy = False
        app.busy_message = ""
        if res.ok:
            app.connection.reset()
            app.account_name = ""
            app.signed_in = False
            self.set_status("Signed out; local credentials cleared.", "ok")
            self.notify("Signed out.", timeout=2)
        else:
            self.set_status("Sign-out failed.", "error")
            self.app.push_screen(
                MessageScreen("Sign-out failed", res.error_text, severity="error")
            )
        self.refresh_all()


# ===========================================================================
# Modal screens
# ===========================================================================


class OrbitModal(ModalScreen[Any]):
    """Shared chrome for all ORBIT dialogs."""

    BINDINGS = [Binding("escape", "close_modal", "Close", show=False)]
    title_text = "ORBIT"
    subtitle = ""
    dialog_class = ""

    def compose(self) -> ComposeResult:
        classes = f"dialog {self.dialog_class}".strip()
        with Vertical(classes=classes):
            with Horizontal(classes="dialog-head"):
                yield Static(self.title_text, classes="dialog-title")
                yield Button("ESC", id="modal-close", classes="btn compact")
            if self.subtitle:
                yield Static(self.subtitle, classes="dialog-sub")
            yield from self.modal_body()
            yield from self.modal_footer()

    def modal_body(self) -> ComposeResult:
        yield Static("")

    def modal_footer(self) -> ComposeResult:
        if False:  # pragma: no cover - keeps this a generator
            yield Static("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "modal-close":
            event.stop()
            self.action_close_modal()

    def action_close_modal(self) -> None:
        self.dismiss(None)


class SearchScreen(OrbitModal):
    title_text = "⌕  FIND A REGION"
    subtitle = "Search by country, code or continent.  Enter selects; Enter on the map connects."

    def __init__(self) -> None:
        super().__init__()
        self._options: list[Country] = []
        self._query = ""

    def modal_body(self) -> ComposeResult:
        with Vertical(classes="dialog-body"):
            with Horizontal(classes="search-row"):
                yield Input(placeholder="Search 149 regions…", id="search-input")
            yield OptionList(id="search-list")

    def modal_footer(self) -> ComposeResult:
        with Horizontal(classes="dialog-footer"):
            yield Static(
                f"[{COL['muted']}]Type to filter · ↑↓ to browse · Enter to select[/]",
                classes="dialog-hint",
            )

    def on_mount(self) -> None:
        self._rebuild()
        self.query_one("#search-input", Input).focus()

    def _rebuild(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        query = normalize_name(self._query)
        scored: list[tuple[float, Country]] = []
        for country in app.country_list:
            if not query:
                scored.append((0.0, country))
                continue
            name = normalize_name(country.name)
            code = country.code.lower()
            continent = normalize_name(country.continent)
            if query == code:
                score = 0.0
            elif name.startswith(query):
                score = 0.1
            elif code.startswith(query):
                score = 0.2
            elif any(word.startswith(query) for word in name.split()):
                score = 0.35
            elif query in name:
                score = 0.6
            elif query in continent:
                score = 0.9
            else:
                continue
            scored.append((score, country))
        scored.sort(key=lambda item: (item[0], item[1].name))
        self._options = [country for _, country in scored]
        option_list = self.query_one("#search-list", OptionList)
        option_list.clear_options()
        for country in self._options:
            text = Text()
            text.append(f"{country.code}  ", style=f"bold {COL['purple_hi']}")
            text.append(country.name, style=COL["text"])
            if country.servers:
                text.append(f"  · {fmt_int(country.servers)}", style=COL["muted"])
                text.append(f" · {country.load}%", style=COL["muted"])
            if country.code in app.excluded_codes:
                text.append("  · auto-excluded", style=COL["red"])
            option_list.add_option(Option(text, id=country.code))
        if self._options:
            option_list.highlighted = 0

    def on_input_changed(self, event: Input.Changed) -> None:
        self._query = event.value
        self._rebuild()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._options:
            self._choose(self._options[0].code)

    @on(OptionList.OptionSelected)
    def _option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "search-list":
            return
        if event.option.id:
            self._choose(event.option.id)

    def _choose(self, code: str) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.select_country(code)
        if app.main_screen is not None:
            if app.main_screen.map is not None:
                app.main_screen.map.ensure_visible(code)
            app.main_screen.set_status(f"Selected {app.countries[code].name}.", "info")
        self.dismiss(code)


class CitiesScreen(OrbitModal):
    title_text = "◫  CITIES"
    subtitle = "City-level servers are read with 'protonvpn cities list'."

    def __init__(self, code: str) -> None:
        super().__init__()
        self.code = code
        self._rows: list[tuple[str, set[str]]] = []
        self._note = ""

    def modal_body(self) -> ComposeResult:
        with Vertical(classes="dialog-body"):
            yield Static("", id="cities-status", classes="note")
            yield OptionList(id="cities-list")

    def modal_footer(self) -> ComposeResult:
        with Horizontal(classes="dialog-footer"):
            yield Button("ENTIRE COUNTRY", id="cities-country", classes="btn ghost")
            yield Static("", classes="grow")
            yield Button("CLOSE", id="cities-close", classes="btn")

    def on_mount(self) -> None:
        country = self.app.countries.get(self.code)  # type: ignore[attr-defined]
        if country:
            title = self.query_one(".dialog-title", Static)
            title.update(f"◫  CITIES IN {country.name.upper()}")
            sub = self.query_one(".dialog-sub", Static)
            sub.update(
                f"{country.name} ({country.code}) · "
                f"{fmt_int(country.servers)} servers · {country.load}% avg load"
            )
        self.query_one("#cities-list", OptionList).focus()
        self.run_worker(self._load(), group="cities")

    async def _load(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        country = app.countries.get(self.code)
        status = self.query_one("#cities-status", Static)
        status.update(f"[{COL['amber']}]◌ Reading cities via protonvpn cities list {self.code}…[/]")
        rows, note = await app.fetch_cities(self.code)
        self._rows = rows
        self._note = note
        if not rows and country:
            rows = [
                (name, set(city.features))
                for name, city in sorted(country.cities.items(), key=lambda item: item[0])
            ]
            self._rows = rows
            note = "CLI returned no city rows; using the cached server network index."
        option_list = self.query_one("#cities-list", OptionList)
        option_list.clear_options()
        current = app.selected_city_name if app.selected_country() and app.selected_country().code == self.code else None
        highlighted = 0
        for index, (name, cli_features) in enumerate(self._rows):
            stats = country.cities.get(name) if country else None
            features = set(cli_features)
            if stats:
                features |= set(stats.features)
            text = Text()
            text.append(name, style=f"bold {COL['text']}")
            if features:
                text.append(" · " + " · ".join(sorted(features)), style=COL["purple_hi"])
            if stats:
                text.append(f" · {fmt_int(stats.servers)}", style=COL["muted"])
                text.append(f" · {stats.load}%", style=COL["muted"])
            if name == current:
                text.append(" · ◆ selected", style=COL["cyan"])
                highlighted = index
            option_list.add_option(Option(text, id=name))
        if self._rows:
            option_list.highlighted = highlighted
        if note:
            status.update(f"[{COL['muted']}]{markup(note)}[/]")
        elif rows:
            status.update(
                f"[{COL['muted']}]Click a city to select it, then press ENTER on the map to connect.[/]"
            )
        else:
            status.update(f"[{COL['warn']}]No city-level servers were reported for this region.[/]")

    @on(OptionList.OptionSelected)
    def _city_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "cities-list":
            return
        name = event.option.id
        if not name:
            return
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.select_country(self.code, city=name)
        app.main_screen.set_status(f"City selected: {name}. Press ENTER to connect.", "info")
        self.dismiss(name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cities-country":
            app: "OrbitApp" = self.app  # type: ignore[assignment]
            app.select_country(self.code, city=None)
            app.main_screen.set_status("Whole region selected.", "info")
            self.dismiss(None)
        elif event.button.id == "cities-close":
            self.dismiss(None)
        else:
            super().on_button_pressed(event)


class ServerIDScreen(OrbitModal):
    title_text = "⌗  CONNECT TO A SERVER ID"
    subtitle = "Use any logical server ID from your Proton account, for example IT#23 or CH#18-TOR."

    def modal_body(self) -> ComposeResult:
        with Vertical(classes="dialog-body"):
            with Horizontal(classes="search-row"):
                yield Input(placeholder="Server ID…", id="server-id-input")
            yield Static(
                f"[{COL['muted']}]Server IDs are available at "
                "account.proton.me/vpn/WireGuard. CLI examples:[/]",
                classes="note",
            )
            yield Static(
                f"[{COL['purple_hi']}]protonvpn connect IT#23[/]\n"
                f"[{COL['purple_hi']}]protonvpn connect CH#18-TOR[/]",
                classes="note",
            )
            yield Static("", id="server-id-error", classes="error")

    def modal_footer(self) -> ComposeResult:
        with Horizontal(classes="dialog-footer"):
            yield Static("", classes="grow")
            yield Button("CONNECT", id="server-connect", classes="btn primary")

    def on_mount(self) -> None:
        self.query_one("#server-id-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._connect()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "server-connect":
            self._connect()
        else:
            super().on_button_pressed(event)

    def _connect(self) -> None:
        value = self.query_one("#server-id-input", Input).value.strip().upper()
        if not re.match(r"^[A-Za-z]{2}(?:-[A-Za-z]{2})?#[\w-]+$", value):
            self.query_one("#server-id-error", Static).update(
                f"[{COL['red']}]Expected a server ID such as IT#23.[/]"
            )
            return
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        code_matches = re.findall(r"([A-Za-z]{2})(?=#|-[A-Za-z]{2}#)", value)
        code = code_matches[-1].upper() if code_matches else ""
        target = None
        if code and code in app.countries:
            app.select_country(code)
            target = app.place_for_country(app.countries[code])
            target["label"] = value
        self.dismiss(value)
        app.main_screen.start_connect(["connect", value], target=target)


class SettingsScreen(OrbitModal):
    title_text = "⚙  CLI SETTINGS"
    subtitle = "Every change is applied with 'protonvpn config set'. Changes are serialized through the CLI."

    def __init__(self, settings: dict[str, str]) -> None:
        super().__init__()
        self.settings = settings
        self._applying = False
        self._initial = self._normalize_initial()
        self._custom_dns_toggle: Optional[Toggle] = None
        self._status: Optional[Static] = None

    # --------------------------------------------------------------- parsing

    def _upgrade(self, key: str) -> bool:
        return "upgrade" in (self.settings.get(key) or "").lower()

    def _normalize_initial(self) -> dict[str, Any]:
        netshield = (self.settings.get("netshield") or "off").strip().lower()
        if netshield not in {"off", "malware-only", "malware-ads-trackers"}:
            netshield = "off"
        killswitch = (self.settings.get("kill-switch") or "off").strip().lower()
        if killswitch not in {"off", "standard"}:
            killswitch = "off"
        dns_raw = self.settings.get("custom-dns") or "off"
        dns_enabled = dns_raw.strip().lower().startswith("on")
        return {
            "netshield": netshield,
            "kill-switch": killswitch,
            "port-forwarding": (self.settings.get("port-forwarding") or "off").strip().lower() == "on",
            "custom-dns": dns_enabled,
            "custom-dns-list": parse_dns_value(dns_raw),
            "vpn-accelerator": (self.settings.get("vpn-accelerator") or "off").strip().lower() == "on",
            "moderate-nat": (self.settings.get("moderate-nat") or "off").strip().lower() == "on",
            "ipv6": (self.settings.get("ipv6") or "off").strip().lower() == "on",
            "anonymous-crash-reports": (
                self.settings.get("anonymous-crash-reports") or "off"
            ).strip().lower() == "on",
        }

    # ---------------------------------------------------------------- compose

    def _row(self, name: str, desc: str, control: Widget) -> ComposeResult:
        with Horizontal(classes="setting-row"):
            with Vertical(classes="setting-main"):
                yield Static(name, classes="setting-name", markup=False)
                yield Static(desc, classes="setting-desc")
            with Horizontal(classes="setting-control"):
                yield control

    def modal_body(self) -> ComposeResult:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        notes = []
        if app.connection.connected:
            notes.append(
                f"[{COL['amber']}]Connected: Kill Switch is locked until you disconnect. "
                "Custom DNS / IPv6 take effect on the next connection.[/]"
            )
        if any(self._upgrade(key) for key in self.settings):
            notes.append(f"[{COL['warn']}]Some features require a higher plan (shown as Upgrade).[/]")
        with Vertical(classes="dialog-body"):
            if notes:
                yield Static("\n".join(notes), classes="note")
            with VerticalScroll(classes="settings-list"):
                yield from self._row(
                    "NetShield",
                    "Ad, tracker and malware blocking at DNS level",
                    Choice(
                        "netshield",
                        [
                            ("off", "OFF"),
                            ("malware-only", "MALWARE"),
                            ("malware-ads-trackers", "MALWARE + ADS"),
                        ],
                        self._initial["netshield"],
                        locked=self._upgrade("netshield"),
                        id="settings-netshield",
                    ),
                )
                yield from self._row(
                    "Kill Switch",
                    "Block internet traffic if the VPN drops"
                    + (" — disconnect required" if app.connection.connected else ""),
                    Choice(
                        "kill-switch",
                        [("off", "OFF"), ("standard", "STANDARD")],
                        self._initial["kill-switch"],
                        locked=self._upgrade("kill-switch") or app.connection.connected,
                        id="settings-killswitch",
                    ),
                )
                yield from self._row(
                    "Port forwarding",
                    "Request a forwarded port when connected to P2P",
                    Toggle(self._initial["port-forwarding"], id="toggle-port-forwarding"),
                )
                yield from self._row(
                    "Custom DNS",
                    "Use your own resolvers instead of Proton DNS",
                    self._dns_control(),
                )
                yield from self._row(
                    "VPN Accelerator",
                    "Performance optimization for long-distance routes",
                    Toggle(self._initial["vpn-accelerator"], id="toggle-vpn-accelerator"),
                )
                yield from self._row(
                    "Moderate NAT",
                    "Better connectivity for gaming and P2P",
                    Toggle(self._initial["moderate-nat"], id="toggle-moderate-nat"),
                )
                yield from self._row(
                    "IPv6",
                    "Route IPv6 through the tunnel",
                    Toggle(self._initial["ipv6"], id="toggle-ipv6"),
                )
                yield from self._row(
                    "Anonymous crash reports",
                    "Send anonymous diagnostics to Proton",
                    Toggle(self._initial["anonymous-crash-reports"], id="toggle-anonymous-crash-reports"),
                )

    def _dns_control(self) -> Widget:
        return _DNSEditor(self._initial["custom-dns"], ", ".join(self._initial["custom-dns-list"]))

    def modal_footer(self) -> ComposeResult:
        with Horizontal(classes="dialog-footer"):
            self._status = Static(
                f"[{COL['muted']}]Changes are written one CLI command at a time.[/]",
                id="settings-status",
                classes="note",
            )
            yield self._status
            yield Button("APPLY CHANGES", id="settings-apply", classes="btn primary")
            yield Button("CLOSE", id="settings-close", classes="btn")

    # ----------------------------------------------------------------- apply

    def _collect(self) -> tuple[dict[str, Any], list[list[str]], Optional[str]]:
        netshield = self.query_one("#settings-netshield", Choice).value
        killswitch = self.query_one("#settings-killswitch", Choice).value
        port = self.query_one("#toggle-port-forwarding", Toggle).value
        accel = self.query_one("#toggle-vpn-accelerator", Toggle).value
        moderate = self.query_one("#toggle-moderate-nat", Toggle).value
        ipv6 = self.query_one("#toggle-ipv6", Toggle).value
        crash = self.query_one("#toggle-anonymous-crash-reports", Toggle).value
        dns_editor = self.query_one("#dns-editor", _DNSEditor)
        dns_on = dns_editor.value
        dns_text = dns_editor.dns_text
        if dns_on and not dns_text:
            return {}, [], "Custom DNS is enabled but no DNS servers were provided."
        current = {
            "netshield": netshield,
            "kill-switch": killswitch,
            "port-forwarding": port,
            "custom-dns": dns_on,
            "custom-dns-list": [part.strip() for part in dns_text.split(",") if part.strip()] if dns_on else [],
            "vpn-accelerator": accel,
            "moderate-nat": moderate,
            "ipv6": ipv6,
            "anonymous-crash-reports": crash,
        }
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.connection.connected and current["kill-switch"] != self._initial["kill-switch"]:
            return {}, [], "Disconnect before changing Kill Switch."
        commands: list[list[str]] = []
        if current["netshield"] != self._initial["netshield"]:
            commands.append(["config", "set", "netshield", current["netshield"]])
        if current["kill-switch"] != self._initial["kill-switch"]:
            commands.append(["config", "set", "kill-switch", current["kill-switch"]])
        if current["port-forwarding"] != self._initial["port-forwarding"]:
            commands.append(
                ["config", "set", "port-forwarding", "on" if current["port-forwarding"] else "off"]
            )
        if current["custom-dns"] != self._initial["custom-dns"] or (
            current["custom-dns"] and current["custom-dns-list"] != self._initial["custom-dns-list"]
        ):
            if current["custom-dns"]:
                commands.append(
                    [
                        "config",
                        "set",
                        "custom-dns",
                        "on",
                        "--dns",
                        ",".join(current["custom-dns-list"]),
                    ]
                )
            else:
                commands.append(["config", "set", "custom-dns", "off"])
        for key in ("vpn-accelerator", "moderate-nat", "ipv6", "anonymous-crash-reports"):
            if current[key] != self._initial[key]:
                commands.append(["config", "set", key, "on" if current[key] else "off"])
        return current, commands, None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-apply":
            self._apply()
        elif event.button.id == "settings-close":
            self.dismiss(None)
        else:
            super().on_button_pressed(event)

    def _apply(self) -> None:
        if self._applying:
            return
        current, commands, error = self._collect()
        status = self.query_one("#settings-status", Static)
        if error:
            status.update(f"[{COL['red']}]{markup(error)}[/]")
            return
        if not commands:
            status.update(f"[{COL['muted']}]No changes to apply.[/]")
            return
        self.run_worker(self._apply_worker(current, commands), group="settings")

    async def _apply_worker(self, current: dict[str, Any], commands: list[list[str]]) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        self._applying = True
        app.busy = True
        app.busy_message = "Writing settings through the CLI…"
        app.main_screen.refresh_all()
        status = self.query_one("#settings-status", Static)
        apply_btn = self.query_one("#settings-apply", Button)
        apply_btn.disabled = True
        failed = False
        for index, command in enumerate(commands, start=1):
            status.update(
                f"[{COL['amber']}]◌ {index}/{len(commands)} · protonvpn {' '.join(command)}[/]"
            )
            res = await app.cli.run(*command, timeout=75)
            if not res.ok:
                failed = True
                status.update(
                    f"[{COL['red']}]✕ {markup(command[-1])} failed: {markup(res.error_text)}[/]"
                )
                app.main_screen.set_status("Setting change failed — see ACTIVITY.", "error")
                break
        if not failed:
            self._initial = dict(current)
            self._initial["custom-dns-list"] = list(current["custom-dns-list"])
            status.update(
                f"[{COL['green']}]✓ Applied {len(commands)} setting change(s).[/]\n"
                f"[{COL['muted']}]Custom DNS and IPv6 take effect on the next connection.[/]"
            )
            app.main_screen.set_status("CLI settings applied.", "ok")
            app.main_screen.notify("Settings applied through protonvpn CLI.", timeout=2.5)
        app.busy = False
        app.busy_message = ""
        app.main_screen.refresh_all()
        apply_btn.disabled = False
        self._applying = False


class _DNSEditor(Widget):
    """A custom DNS toggle plus text field that survives re-renders."""

    def __init__(self, enabled: bool, dns: str = "") -> None:
        super().__init__(id="dns-editor")
        self.value = enabled
        self.dns_text = dns

    def compose(self) -> ComposeResult:
        yield Input(
            value=self.dns_text,
            placeholder="1.1.1.1, 8.8.8.8",
            id="dns-input",
            classes="dns-input",
        )
        yield Toggle(self.value, id="toggle-custom-dns")

    def on_toggle_changed(self, message: Toggle.Changed) -> None:
        message.stop()
        if message.toggle.id == "toggle-custom-dns":
            self.value = message.value

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "dns-input":
            self.dns_text = event.value


class AutoconnectScreen(OrbitModal):
    title_text = "⟳  AUTOCONNECT POLICY"
    subtitle = (
        "AutoConnect uses the CLI to connect to the fastest server in one allowed region. "
        "Excluded regions are never chosen automatically."
    )
    dialog_class = "wide"

    def __init__(self, focus_exclusions: bool = False) -> None:
        super().__init__()
        self.focus_exclusions = focus_exclusions
        self._query = ""
        self._excl_list: Optional[OptionList] = None
        self._excl_count: Optional[Static] = None
        self._status: Optional[Static] = None
        self._preferred: Optional[Select] = None

    # ---------------------------------------------------------------- compose

    def modal_body(self) -> ComposeResult:
        with Horizontal(classes="split dialog-body"):
            with Vertical(classes="split-left"):
                yield Static(f"[bold {COL['muted']}]LAUNCH BEHAVIOUR[/]", classes="note")
                with Horizontal(classes="setting-row"):
                    with Vertical(classes="setting-main"):
                        yield Static("Autoconnect on launch", classes="setting-name", markup=False)
                        yield Static("Connect when ORBIT starts", classes="setting-desc")
                    with Horizontal(classes="setting-control"):
                        yield Toggle(
                            bool(self.app.config["autoconnect"].get("enabled")),  # type: ignore[attr-defined]
                            id="auto-enabled",
                        )
                yield Static(f"[bold {COL['muted']}]PREFERRED REGION[/]", classes="note")
                yield Select(
                    self._preferred_options(),
                    value=self._preferred_value(),
                    allow_blank=False,
                    id="auto-preferred",
                    compact=True,
                )
                yield Static(self._policy_text(), id="auto-policy", classes="note")
                yield Static("", id="auto-status", classes="note")

            with Vertical(classes="split-right"):
                with Horizontal(classes="search-row slim"):
                    yield Static(f"[bold {COL['muted']}]EXCLUSIONS[/]", id="excl-title")
                    yield Static("", id="excl-count", classes="count-badge")
                    yield Static("", classes="grow")
                    yield Button("CLEAR ALL", id="excl-clear", classes="btn compact")
                with Horizontal(classes="search-row slim"):
                    yield Input(
                        placeholder="Filter regions to exclude…",
                        id="excl-search",
                    )
                yield OptionList(id="excl-list")

    def modal_footer(self) -> ComposeResult:
        with Horizontal(classes="dialog-footer"):
            yield Static(
                f"[{COL['muted']}]Click to toggle exclusion.[/]",
                classes="dialog-hint",
            )
            yield Button(
                "USE SELECTED",
                id="auto-use-selected",
                classes="btn compact",
            )
            yield Button("⚡  AUTOCONNECT NOW", id="auto-now", classes="btn primary")

    # ---------------------------------------------------------------- helpers

    def _preferred_options(self) -> list[tuple[str, str]]:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        options: list[tuple[str, str]] = [("Any allowed region", "__any__")]
        for country in sorted(app.country_list, key=lambda item: item.name):
            if country.code in app.excluded_codes:
                continue
            suffix = f"  · {country.load}%" if country.load else ""
            options.append((f"{country.name} ({country.code}){suffix}", country.code))
        return options

    def _preferred_value(self) -> str:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        preferred = app.config["autoconnect"].get("preferred") or ""
        if preferred and preferred not in app.excluded_codes and preferred in app.countries:
            return preferred
        return "__any__"

    def _policy_text(self) -> str:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        preferred = self._preferred_value()
        if preferred == "__any__":
            return (
                f"[{COL['muted']}]Weighted random choice among allowed regions, "
                "biased by capacity and current load.[/]"
            )
        country = app.countries.get(preferred)
        name = country.name if country else preferred
        return f"[{COL['muted']}]Always choose {markup(name)} when it is allowed.[/]"

    def on_mount(self) -> None:
        self._excl_list = self.query_one("#excl-list", OptionList)
        self._excl_count = self.query_one("#excl-count", Static)
        self._status = self.query_one("#auto-status", Static)
        self._preferred = self.query_one("#auto-preferred", Select)
        self._rebuild_exclusions()
        if self.focus_exclusions:
            self.query_one("#excl-search", Input).focus()
        else:
            self._excl_list.focus()

    # ------------------------------------------------------------- exclusions

    def _filtered_countries(self) -> list[Country]:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        query = normalize_name(self._query)
        countries = list(app.country_list)
        if query:
            countries = [
                c for c in countries
                if query in normalize_name(c.name)
                or query in c.code.lower()
                or query in normalize_name(c.continent)
            ]
        return sorted(countries, key=lambda c: c.name)

    def _rebuild_exclusions(self, highlight: Optional[str] = None) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if self._excl_list is None:
            return
        self._excl_list.clear_options()
        countries = self._filtered_countries()
        highlight_index = 0
        for index, country in enumerate(countries):
            excluded = country.code in app.excluded_codes
            line = Text()
            line.append("▣ " if excluded else "▢ ", style=COL["red"] if excluded else COL["muted"])
            line.append(country.name, style=f"bold {COL['text'] if excluded else COL['text_dim']}")
            line.append(f"  · {country.code}", style=COL["purple_hi"])
            if country.servers:
                line.append(f" · {fmt_int(country.servers)}", style=COL["muted"])
                line.append(f" · {country.load}%", style=COL["muted"])
            self._excl_list.add_option(Option(line, id=country.code))
            if country.code == highlight:
                highlight_index = index
        if countries:
            self._excl_list.highlighted = highlight_index
        if self._excl_count is not None:
            self._excl_count.update(str(len(app.excluded_codes)))
        if self._status is not None:
            if len(app.excluded_codes) >= max(1, len(app.country_list)):
                self._status.update(
                    f"[{COL['red']}]All regions are excluded. AutoConnect cannot run.[/]"
                )
            else:
                self._status.update("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "excl-search":
            self._query = event.value
            self._rebuild_exclusions()

    @on(OptionList.OptionSelected)
    def _exclusion_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "excl-list" or not event.option.id:
            return
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        code = event.option.id
        now_excluded = code not in app.excluded_codes
        app.set_excluded(code, now_excluded)
        if now_excluded and (app.config["autoconnect"].get("preferred") or "") == code:
            app.config["autoconnect"]["preferred"] = ""
            app.save_preferences()
        if self._preferred is not None:
            self._preferred.set_options(self._preferred_options())
            self._preferred.value = self._preferred_value()
        self.query_one("#auto-policy", Static).update(self._policy_text())
        self._rebuild_exclusions(highlight=code)
        app.main_screen.refresh_all()

    def on_toggle_changed(self, message: Toggle.Changed) -> None:
        message.stop()
        if message.toggle.id != "auto-enabled":
            return
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        app.config["autoconnect"]["enabled"] = message.value
        app.save_preferences()
        app.main_screen.refresh_cards()
        if self._status is not None:
            self._status.update(
                f"[{COL['green'] if message.value else COL['muted']}]"
                f"AutoConnect is {'ON' if message.value else 'OFF'}.[/]"
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "auto-preferred":
            return
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        value = str(event.value)
        app.config["autoconnect"]["preferred"] = "" if value == "__any__" else value
        app.save_preferences()
        self.query_one("#auto-policy", Static).update(self._policy_text())
        app.main_screen.refresh_cards()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if button_id == "auto-now":
            if not app.allowed_countries():
                if self._status is not None:
                    self._status.update(
                        f"[{COL['red']}]No allowed regions. Clear at least one exclusion.[/]"
                    )
                return
            self.dismiss(None)
            app.main_screen.start_autoconnect(launch=False)
            return
        if button_id == "excl-clear":
            for code in list(app.excluded_codes):
                app.set_excluded(code, False)
            app.config["autoconnect"]["preferred"] = ""
            app.save_preferences()
            if self._preferred is not None:
                self._preferred.set_options(self._preferred_options())
                self._preferred.value = self._preferred_value()
            self.query_one("#auto-policy", Static).update(self._policy_text())
            self._rebuild_exclusions()
            app.main_screen.refresh_all()
            return
        if button_id == "auto-use-selected":
            selected = app.selected_country()
            if selected is None:
                if self._status is not None:
                    self._status.update(f"[{COL['amber']}]Select a region on the map first.[/]")
                return
            if selected.code in app.excluded_codes:
                if self._status is not None:
                    self._status.update(
                        f"[{COL['amber']}]That region is excluded. Allow it first.[/]"
                    )
                return
            app.config["autoconnect"]["preferred"] = selected.code
            app.save_preferences()
            if self._preferred is not None:
                self._preferred.value = selected.code
            self.query_one("#auto-policy", Static).update(self._policy_text())
            if self._status is not None:
                self._status.update(
                    f"[{COL['green']}]Preferred region set to {markup(selected.name)}.[/]"
                )
            app.main_screen.refresh_cards()
            return
        super().on_button_pressed(event)


class AccountScreen(OrbitModal):
    title_text = "◇  ACCOUNT & SOURCE"
    subtitle = "Account operations are performed by 'protonvpn signin', 'protonvpn signout' and 'protonvpn info'."
    dialog_class = "wide"

    def __init__(self) -> None:
        super().__init__()
        self.totp = False
        self._summary: Optional[Static] = None
        self._servers: Optional[Static] = None
        self._source: Optional[Static] = None
        self._source_status: Optional[Static] = None

    def modal_body(self) -> ComposeResult:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        with VerticalScroll(classes="dialog-body"):
            yield Static("", id="account-summary", classes="panel")
            yield Static("", id="servers-info", classes="note")
            yield Static("", id="source-info", classes="panel")
            with Horizontal(classes="dialog-footer"):
                yield Button("REFINE VIA IP", id="source-ip", classes="btn compact")
                yield Button("USE TIMEZONE", id="source-tz", classes="btn compact")
                yield Static("", id="source-status", classes="note")
            if app.signed_in:
                yield Static(
                    f"[{COL['muted']}]Signed in. The CLI requires a sign-out before switching accounts.[/]",
                    classes="note",
                )
                with Horizontal(classes="dialog-footer"):
                    yield Button("SIGN OUT VIA CLI", id="account-signout", classes="btn danger")
                    yield Static("", classes="grow")
                    yield Button("REFRESH", id="account-refresh", classes="btn ghost")
            else:
                yield Static(
                    f"[bold {COL['muted']}]SIGN IN[/]\n"
                    f"[{COL['text_dim']}]The password and any 2FA prompt will appear in your terminal. "
                    "ORBIT suspends its screen while the official CLI runs.[/]",
                    classes="note",
                )
                with Horizontal(classes="search-row"):
                    yield Input(placeholder="Proton account username…", id="signin-username")
                    yield Toggle(False, on_label="2FA", off_label="2FA", id="signin-totp")
                yield Static("", id="signin-status", classes="note")
            yield Static(
                f"[{COL['muted']}]CLI BINARY[/]  [{COL['text']}]{markup(CLI_BIN or 'not found')}[/]\n"
                f"[{COL['muted']}]CONFIG[/]      [{COL['text']}]{markup(str(ORBIT_CONFIG_FILE))}[/]\n"
                f"[{COL['muted']}]CACHE[/]       [{COL['text']}]{markup(str(ORBIT_CACHE_DIR))}[/]",
                classes="tiny",
            )

    def modal_footer(self) -> ComposeResult:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        with Horizontal(classes="dialog-footer"):
            yield Static(
                f"[{COL['muted']}]Source location only shapes the route drawing.[/]",
                classes="dialog-hint",
            )
            if not app.signed_in:
                yield Button("SIGN IN VIA CLI", id="account-signin", classes="btn primary")
            yield Button("CLOSE", id="account-close", classes="btn")

    def on_mount(self) -> None:
        self._summary = self.query_one("#account-summary", Static)
        self._servers = self.query_one("#servers-info", Static)
        self._source = self.query_one("#source-info", Static)
        self._source_status = self.query_one("#source-status", Static)
        self._render_source()
        self._render_summary()
        self.run_worker(self._load(), group="account")

    def _render_summary(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if self._summary is None:
            return
        signed = "● SIGNED IN" if app.signed_in else ("○ SIGNED OUT" if app.signed_in is False else "◌ UNKNOWN")
        color = COL["green"] if app.signed_in else COL["text_dim"]
        account = markup(app.account_name or "—")
        self._summary.update(
            f"[bold {COL['muted']}]ACCOUNT[/]\n"
            f"[bold {COL['text']}]{account}[/]\n"
            f"[{color}]{signed}[/]  "
            f"[{COL['muted']}]· CLI status is the source of truth[/]"
        )

    def _render_source(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if self._source is None:
            return
        kind = "IP lookup" if app.home.kind == "ip" else "system timezone"
        self._source.update(
            f"[bold {COL['muted']}]SOURCE LOCATION[/]\n"
            f"[{COL['cyan']}]◉[/] [{COL['text']}]{markup(app.home.label)}[/]  "
            f"[{COL['muted']}]· {kind}[/]\n"
            f"[{COL['muted']}]lat {app.home.lat:.2f}  ·  lon {app.home.lon:.2f}[/]"
        )

    async def _load(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if self._servers is not None:
            self._servers.update(f"[{COL['amber']}]◌ Reading account via protonvpn info…[/]")
        try:
            await app.refresh_account()
            self._render_summary()
        except Exception:
            pass
        res = await app.cli.run("servers", timeout=20)
        if self._servers is not None:
            if res.ok and res.text:
                text = res.text
                match = re.search(r"https?://\S+", text)
                url = match.group(0) if match else ""
                self._servers.update(
                    f"[{COL['muted']}]protonvpn servers[/]  ·  "
                    f"[{COL['purple_hi']}]{markup(url or text)}[/]"
                )
            else:
                self._servers.update(
                    f"[{COL['muted']}]protonvpn servers[/]  ·  "
                    f"[{COL['text_dim']}]{markup(res.error_text)}[/]"
                )
        self._render_source()

    def on_toggle_changed(self, message: Toggle.Changed) -> None:
        message.stop()
        if message.toggle.id == "signin-totp":
            self.totp = message.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "signin-username":
            self._start_signin()

    def _start_signin(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        username = self.query_one("#signin-username", Input).value.strip()
        status = self.query_one("#signin-status", Static)
        if not username:
            status.update(f"[{COL['red']}]Enter your Proton username first.[/]")
            return
        self.dismiss(None)
        app.main_screen.run_worker(
            app.main_screen.signin_interactive(username, self.totp),
            group="op",
            exclusive=True,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        button_id = event.button.id
        if button_id == "account-close":
            self.dismiss(None)
            return
        if button_id == "account-refresh":
            self.run_worker(self._load(), group="account")
            return
        if button_id == "account-signin":
            self._start_signin()
            return
        if button_id == "account-signout":
            self.app.push_screen(
                ConfirmScreen(
                    "Sign out of Proton VPN?",
                    "This clears local credentials. If the VPN is connected, the CLI will terminate the tunnel.",
                    confirm_label="SIGN OUT",
                    danger=True,
                ),
                self._signout_confirmed,
            )
            return
        if button_id == "source-ip":
            self.run_worker(self._refine_ip(), group="source")
            return
        if button_id == "source-tz":
            app.set_home_timezone()
            self._render_source()
            app.main_screen.refresh_all()
            if self._source_status is not None:
                self._source_status.update(f"[{COL['green']}]Using system timezone.[/]")
            return
        super().on_button_pressed(event)

    def _signout_confirmed(self, confirmed: Optional[bool]) -> None:
        if not confirmed:
            return
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        self.dismiss(None)
        app.main_screen.run_worker(
            app.main_screen.signout_cli(), group="op", exclusive=True
        )

    async def _refine_ip(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if app.connection.connected:
            if self._source_status is not None:
                self._source_status.update(
                    f"[{COL['amber']}]Refine while disconnected; IP lookup would see the VPN exit.[/]"
                )
            return
        if self._source_status is not None:
            self._source_status.update(f"[{COL['amber']}]◌ Asking ipinfo.io…[/]")
        result = await app.refine_home_via_ip()
        self._render_source()
        app.main_screen.refresh_all()
        if self._source_status is not None:
            if result is None:
                self._source_status.update(
                    f"[{COL['red']}]IP lookup failed. Keeping the timezone estimate.[/]"
                )
            else:
                self._source_status.update(
                    f"[{COL['green']}]Source refined to {markup(result.label)}.[/]"
                )


class ActivityScreen(OrbitModal):
    title_text = "≡  ACTIVITY · CLI OUTPUT"
    subtitle = "Every VPN action is visible here, including the exact protonvpn command line."
    dialog_class = "wide"

    def __init__(self) -> None:
        super().__init__()
        self._body: Optional[Static] = None
        self._scroll: Optional[VerticalScroll] = None
        self._seen = -1

    def modal_body(self) -> ComposeResult:
        with Vertical(classes="dialog-body"):
            with VerticalScroll(id="activity-scroll"):
                yield Static("", id="activity-body")

    def modal_footer(self) -> ComposeResult:
        with Horizontal(classes="dialog-footer"):
            yield Button("CLEAR", id="activity-clear", classes="btn ghost")
            yield Static("", classes="grow")
            yield Button("CLOSE", id="activity-close", classes="btn")

    def on_mount(self) -> None:
        self._body = self.query_one("#activity-body", Static)
        self._scroll = self.query_one("#activity-scroll", VerticalScroll)
        self._render_log()
        self.set_interval(0.5, self._refresh_if_changed)

    def _render_log(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if self._body is None:
            return
        if not app.activity:
            self._body.update(
                f"[{COL['muted']}]No activity yet. Connect, disconnect or change a setting "
                "and the CLI command will appear here.[/]"
            )
            self._seen = 0
            return
        lines: list[str] = []
        for entry in app.activity[-160:]:
            stamp = datetime.fromtimestamp(entry.ts).strftime("%H:%M:%S")
            icon = f"[{COL['green']}]✓[/]" if entry.ok else f"[{COL['red']}]✕[/]"
            lines.append(
                f"[{COL['muted']}]{stamp}[/]  {icon}  "
                f"[bold {COL['text']}]{markup(entry.command)}[/]"
            )
            if entry.output:
                for line in entry.output.splitlines()[:35]:
                    lines.append(f"      [{COL['text_dim']}]{markup(line)}[/]")
            lines.append("")
        self._body.update("\n".join(lines))
        self._seen = len(app.activity)
        if self._scroll is not None:
            self.call_after_refresh(self._scroll.scroll_end, animate=False)

    def _refresh_if_changed(self) -> None:
        app: "OrbitApp" = self.app  # type: ignore[assignment]
        if len(app.activity) != self._seen:
            self._render_log()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "activity-clear":
            app: "OrbitApp" = self.app  # type: ignore[assignment]
            app.activity.clear()
            self._render_log()
            return
        if event.button.id == "activity-close":
            self.dismiss(None)
            return
        super().on_button_pressed(event)


class HelpScreen(OrbitModal):
    title_text = "?  HELP · KEY MAP & CLI PARITY"
    subtitle = "PROTON ORBIT is a front-end for the installed protonvpn CLI; no VPN logic is reimplemented."
    dialog_class = "wide"

    def modal_body(self) -> ComposeResult:
        with VerticalScroll(classes="dialog-body"):
            yield Static(self._help_text())

    def modal_footer(self) -> ComposeResult:
        with Horizontal(classes="dialog-footer"):
            yield Static("", classes="grow")
            yield Button("CLOSE", id="help-close", classes="btn")

    def _help_text(self) -> str:
        return f"""
[bold {COL['purple_hi']}]MAP & NAVIGATION[/]
[{COL['purple_hi']}]↑ ↓ ← →[/]      Select the nearest region in that direction
[{COL['purple_hi']}]mouse click[/]   Select a region on the map (double-click connects)
[{COL['purple_hi']}]mouse wheel[/]   Zoom around the pointer
[{COL['purple_hi']}]+ / - / 0[/]     Zoom in / out / reset to world
[{COL['purple_hi']}]ENTER[/]         Connect to the selected country or city
[{COL['purple_hi']}]C[/]             Quick Connect: fastest server globally
[{COL['purple_hi']}]D[/]             Disconnect
[{COL['purple_hi']}]ESC[/]           Clear a selected city, then reset zoom

[bold {COL['purple_hi']}]FEATURE FILTERS[/]
[{COL['purple_hi']}]P[/] P2P     [{COL['purple_hi']}]U[/] Secure Core     [{COL['purple_hi']}]T[/] Tor     [{COL['purple_hi']}]R[/] Random
Filters are passed to the CLI as --p2p, --securecore, --tor and --random.

[bold {COL['purple_hi']}]FIND, CITIES & ACCOUNT[/]
[{COL['purple_hi']}]F[/]  Find region by name / code / continent
[{COL['purple_hi']}]X[/]  Cities for the selected region
[{COL['purple_hi']}]A[/]  AutoConnect policy and exclusions
[{COL['purple_hi']}]E[/]  Same screen, focused on excluded regions
[{COL['purple_hi']}]S[/]  CLI settings (all eight config keys)
[{COL['purple_hi']}]I[/]  Account, sign-in/out and source location
[{COL['purple_hi']}]V[/]  Connect to a specific server ID (for example IT#23)
[{COL['purple_hi']}]L[/]  Activity log with raw CLI output
[{COL['purple_hi']}]Q[/]  Quit

[bold {COL['purple_hi']}]AUTOCONNECT EXCLUSIONS[/]
AutoConnect chooses one allowed region (weighted by capacity and load), then asks
the CLI for the fastest server in that region. Excluded regions are never chosen.
Manual connects are not restricted. Toggle a region from the map's region card or
from the AUTOCONNECT screen. Excluded markers are dim red on the map.

[bold {COL['purple_hi']}]CLI PARITY[/]
[bold {COL['text']}]protonvpn signin / signout / info[/]        ACCOUNT
[bold {COL['text']}]protonvpn connect[/]                        ENTER / QUICK / SERVER ID
[bold {COL['text']}]protonvpn connect --country/--city[/]       map selection / CITIES
[bold {COL['text']}]protonvpn connect --p2p/--securecore/--tor[/] feature pills
[bold {COL['text']}]protonvpn connect --random[/]               RANDOM pill
[bold {COL['text']}]protonvpn disconnect / status[/]            D / status polling
[bold {COL['text']}]protonvpn servers[/]                        ACCOUNT (link)
[bold {COL['text']}]protonvpn countries list[/]                 embedded map refresh
[bold {COL['text']}]protonvpn cities list[/]                    CITIES
[bold {COL['text']}]protonvpn config list / set[/]              SETTINGS

[bold {COL['purple_hi']}]FILES[/]
Config   [{COL['text']}]{markup(str(ORBIT_CONFIG_FILE))}[/]
Cache    [{COL['text']}]{markup(str(ORBIT_CACHE_DIR))}[/]
CLI      [{COL['text']}]{markup(CLI_BIN or 'not found')}[/]

[{COL['muted']}]Free-plan limitations and 2FA requirements come directly from the CLI
and are shown in the activity log and error dialogs.[/]
"""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss(None)
        else:
            super().on_button_pressed(event)


class MessageScreen(OrbitModal):
    dialog_class = "small"

    def __init__(
        self,
        title: str,
        body: str,
        severity: str = "error",
        hint: str = "",
    ) -> None:
        super().__init__()
        self.title_text = title
        self.body_text = body
        self.severity = severity
        self.hint = hint

    def modal_body(self) -> ComposeResult:
        color = {
            "error": COL["red"],
            "warning": COL["amber"],
            "ok": COL["green"],
            "information": COL["cyan"],
        }.get(self.severity, COL["text_dim"])
        icon = {"error": "✕", "warning": "!", "ok": "✓", "information": "i"}.get(
            self.severity, "i"
        )
        with VerticalScroll(classes="dialog-body"):
            yield Static(
                f"[bold {color}]{icon}[/] [{COL['text_dim']}]{markup(self.body_text)}[/]",
                classes="note",
            )
            if self.hint:
                yield Static("", classes="note")
                yield Static(f"[{COL['muted']}]{markup(self.hint)}[/]", classes="tiny")

    def modal_footer(self) -> ComposeResult:
        with Horizontal(classes="dialog-footer"):
            yield Static("", classes="grow")
            yield Button("OK", id="message-ok", classes="btn primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "message-ok":
            self.dismiss(None)
        else:
            super().on_button_pressed(event)


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]
    dialog_class = "small"

    def __init__(
        self,
        title: str,
        body: str,
        confirm_label: str = "CONFIRM",
        danger: bool = False,
    ) -> None:
        super().__init__()
        self.title_text = title
        self.body_text = body
        self.confirm_label = confirm_label
        self.danger = danger

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog small"):
            with Horizontal(classes="dialog-head"):
                yield Static(self.title_text, classes="dialog-title")
                yield Button("ESC", id="confirm-cancel-x", classes="btn compact")
            with VerticalScroll(classes="dialog-body"):
                yield Static(f"[{COL['text_dim']}]{markup(self.body_text)}[/]", classes="note")
            with Horizontal(classes="dialog-footer"):
                yield Static("", classes="grow")
                yield Button("CANCEL", id="confirm-cancel", classes="btn ghost")
                yield Button(
                    self.confirm_label,
                    id="confirm-yes",
                    classes=f"btn {'danger' if self.danger else 'primary'}",
                )

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        elif event.button.id in ("confirm-cancel", "confirm-cancel-x"):
            self.dismiss(False)


# ===========================================================================
# Application
# ===========================================================================


class OrbitApp(App[None]):
    """The single-file Proton VPN TUI."""

    CSS = CSS
    TITLE = APP_TITLE
    SUB_TITLE = "ProtonVPN CLI control deck"

    def __init__(self) -> None:
        super().__init__()
        self.config: dict[str, Any] = load_config()
        self.features: dict[str, bool] = {
            key: bool(value) for key, value in self.config.get("features", {}).items()
        }
        self.excluded_codes: set[str] = set(self.config["autoconnect"].get("excluded") or [])
        self.countries: dict[str, Country] = {}
        self.country_list: list[Country] = []
        self._name_lookup: dict[str, str] = {}
        self._city_lookup: dict[str, str] = {}
        self.server_index: Optional[dict[str, Any]] = None
        self.cities_cache: dict[str, list[tuple[str, set[str]]]] = {}
        self.home: HomeLocation = self._home_from_config()
        self.connection = Connection()
        self.account_name = ""
        self.signed_in: Optional[bool] = None
        self.busy = False
        self.busy_message = ""
        self.pending: Optional[dict[str, Any]] = None
        self.selected_code: Optional[str] = None
        self.selected_city_name: Optional[str] = None
        self.activity: list[ActivityEntry] = []
        self.main_screen: Optional[MainScreen] = None
        self.cli = CLIRunner(CLI_BIN, self._record_cli)
        self._construct_countries()
        self._rebuild_lookups()

    # ------------------------------------------------------------------ setup

    def _construct_countries(self) -> None:
        for code, (name, lat, lon, continent) in COUNTRIES.items():
            self.countries[code] = Country(
                code=code,
                name=name,
                lat=float(lat),
                lon=float(lon),
                continent=continent or "",
            )
        self._sort_countries()

    def _sort_countries(self) -> None:
        self.country_list = sorted(
            self.countries.values(),
            key=lambda c: (c.servers, c.name.lower()),
        )

    def _rebuild_lookups(self) -> None:
        lookup: dict[str, str] = {}
        for country in self.countries.values():
            lookup[normalize_name(country.name)] = country.code
            lookup[country.code.lower()] = country.code
        for name, code in COUNTRY_ALIASES.items():
            if code in self.countries:
                lookup.setdefault(normalize_name(name), code)
        self._name_lookup = lookup
        city_lookup: dict[str, str] = {}
        for country in self.countries.values():
            for city_name in country.cities:
                city_lookup.setdefault(normalize_name(city_name), country.code)
        self._city_lookup = city_lookup

    def _home_from_config(self) -> HomeLocation:
        source = self.config.get("source") or {}
        try:
            lat = float(source.get("lat"))
            lon = float(source.get("lon"))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return HomeLocation(
                    label=str(source.get("label") or "Local"),
                    lat=lat,
                    lon=lon,
                    country_code=str(source.get("country_code") or "").upper(),
                    kind=str(source.get("kind") or "timezone"),
                )
        except (TypeError, ValueError):
            pass
        return timezone_home()

    def on_mount(self) -> None:
        try:
            self.theme = "textual-dark"
        except Exception:
            pass
        self.main_screen = MainScreen()
        self.push_screen(self.main_screen)

    def save_preferences(self) -> None:
        self.config["features"] = dict(self.features)
        self.config["autoconnect"]["excluded"] = sorted(self.excluded_codes)
        try:
            save_config(self.config)
        except Exception as exc:
            self.record_error("save preferences", exc, quiet=True)

    # --------------------------------------------------------------- activity

    def _record_cli(self, entry: ActivityEntry) -> None:
        self.activity.append(entry)
        if len(self.activity) > 300:
            del self.activity[:-300]

    def record_activity_event(self, command: str, ok: bool, output: str) -> None:
        self._record_cli(
            ActivityEntry(
                ts=time.time(),
                command=command,
                ok=ok,
                output=output or "",
            )
        )

    def record_error(self, where: str, exc: BaseException, quiet: bool = False) -> None:
        if not quiet:
            self.record_activity_event(f"ORBIT · {where}", False, f"{type(exc).__name__}: {exc}")

    # ---------------------------------------------------------- account/status

    async def refresh_account(self, force: bool = False) -> bool:
        if self.busy and not force:
            return bool(self.signed_in)
        res = await self.cli.run("info", timeout=30)
        old = self.signed_in
        old_name = self.account_name
        if res.ok:
            match = re.search(r"Account:\s*'([^']*)'", res.text)
            if match:
                self.account_name = match.group(1).strip()
                self.signed_in = bool(self.account_name)
            else:
                self.signed_in = False
                self.account_name = ""
        else:
            if re.search(r"auth|sign in|login", res.error_text, re.IGNORECASE):
                self.signed_in = False
                self.account_name = ""
        changed = old != self.signed_in or old_name != self.account_name
        if self.main_screen is not None:
            self.main_screen.refresh_header()
        return changed

    async def refresh_status(self, record: bool = False, force: bool = False) -> bool:
        if self.busy and not force:
            return False
        res = await self.cli.run("status", timeout=30, record=record)
        if not res.ok:
            if re.search(r"auth|sign in|login", res.error_text, re.IGNORECASE):
                self.signed_in = False
            return False
        fields = parse_status_fields(res.text)
        status_value = (fields.get("status") or "").lower()
        old = (
            self.connection.connected,
            self.connection.server_name,
            self.connection.city,
            self.connection.country_code,
            self.connection.entry_code,
            self.connection.load,
            self.connection.protocol,
        )
        if status_value == "connected":
            server = fields.get("server", "")
            location = fields.get("location", "")
            if " in " in server:
                server, location = server.split(" in ", 1)
                server = server.strip()
                location = location.strip()
            self._apply_connected(server, location, fields)
        else:
            if self.connection.connected:
                self.connection.reset()
        new = (
            self.connection.connected,
            self.connection.server_name,
            self.connection.city,
            self.connection.country_code,
            self.connection.entry_code,
            self.connection.load,
            self.connection.protocol,
        )
        if new != old and self.main_screen is not None:
            self.main_screen.refresh_header()
        return new != old

    def _apply_connected(
        self, server: str, location: str, fields: dict[str, str]
    ) -> None:
        old_server = self.connection.server_name
        was_connected = self.connection.connected
        entry_name = ""
        city_part = location
        if ", via " in location:
            city_part, entry_name = location.split(", via ", 1)
            city_part = city_part.strip()
            entry_name = entry_name.strip()
        city = ""
        country_name = ""
        if "," in city_part:
            city, country_name = city_part.rsplit(",", 1)
            city = city.strip()
            country_name = country_name.strip()
        elif city_part:
            # Secure Core reports "Tokyo, via Sweden" with no exit country;
            # keep the exit city so the route card can still name it.
            if self.resolve_country_code(city_part):
                country_name = city_part.strip()
            else:
                city = city_part.strip()

        prefix_list = re.findall(r"^([A-Za-z]{2})(?:-([A-Za-z]{2}))?#", server)
        prefix_entry = prefix_list[0][0].upper() if prefix_list else ""
        prefix_exit = prefix_list[0][1].upper() if prefix_list and prefix_list[0][1] else ""
        exit_code = prefix_exit or prefix_entry
        if city:
            city_code = self._city_lookup.get(normalize_name(city))
            if city_code:
                exit_code = city_code
        if country_name:
            resolved = self.resolve_country_code(country_name)
            if resolved:
                exit_code = resolved
        entry_code = self.resolve_country_code(entry_name) if entry_name else prefix_entry
        if entry_code == exit_code:
            entry_code = ""
        country = self.countries.get(exit_code)
        entry_country = self.countries.get(entry_code) if entry_code else None
        load = 0
        load_match = re.search(r"(\d+)", fields.get("load", ""))
        if load_match:
            load = int(load_match.group(1))
        protocol = fields.get("protocol", "")
        if not was_connected or old_server != server:
            self.connection.since = time.time()
        if old_server != server:
            self.connection.ip = ""
        self.connection.connected = True
        self.connection.server_name = server
        self.connection.location = location
        self.connection.city = city
        self.connection.country_name = country.name if country else country_name
        self.connection.country_code = exit_code if exit_code in self.countries else ""
        self.connection.entry_country = (
            entry_country.name if entry_country else entry_name
        )
        self.connection.entry_code = entry_code if entry_code in self.countries else ""
        self.connection.load = load
        self.connection.protocol = protocol
        self.connection.raw = self.connection.raw or ""

    def _refresh_main(self) -> None:
        if self.main_screen is not None:
            self.main_screen.refresh_all()

    # --------------------------------------------------------------- countries

    async def load_countries_from_cli(self) -> bool:
        res = await self.cli.run("countries", "list", timeout=120)
        if not res.ok:
            if re.search(r"auth|sign in|login", res.error_text, re.IGNORECASE):
                self.signed_in = False
            return False
        table = parse_country_table(res.text)
        if not table:
            return False
        for code, name in table.items():
            country = self.countries.get(code)
            if country is None:
                lat, lon, continent = 0.0, 0.0, ""
                fallback = COUNTRIES.get(code)
                if fallback:
                    name2, lat, lon, continent = fallback
                    name = name or name2
                country = Country(code=code, name=name, lat=lat, lon=lon, continent=continent)
                self.countries[code] = country
            else:
                country.name = name
        self._rebuild_lookups()
        # The CLI may just have refreshed serverlist.json; enrich from it too.
        try:
            await self.ensure_server_index()
        except Exception as exc:
            self.record_error("server list index", exc, quiet=True)
        self._sort_countries()
        self.ensure_initial_selection()
        self._refresh_main()
        return True

    async def fetch_cities(self, code: str) -> tuple[list[tuple[str, set[str]]], str]:
        """Read city rows from the CLI, then fall back to the cached server index."""
        code = code.strip().upper()
        if code in self.cities_cache:
            return self.cities_cache[code]
        res = await self.cli.run("cities", "list", code, timeout=60)
        rows = parse_city_table(res.text) if res.ok else []
        note = ""
        if not res.ok:
            note = "CLI city lookup failed; showing the cached server network index."
        if not rows:
            country = self.countries.get(code)
            if country and country.cities:
                rows = [
                    (name, set(city.features))
                    for name, city in sorted(country.cities.items(), key=lambda item: item[0])
                ]
                if not note:
                    note = "CLI returned no city rows; using the cached server network index."
        result = (rows, note)
        self.cities_cache[code] = result
        return result

    async def ensure_server_index(self) -> None:
        source = PROTON_SERVERLIST
        cached = load_server_index_cache()
        if cached:
            self.server_index = cached
            apply_server_index(self.countries, cached)
            self._rebuild_lookups()
            self._sort_countries()
        if not source.exists():
            return
        if cache_is_fresh(cached, source):
            self.server_index = cached
            apply_server_index(self.countries, cached)
            self._rebuild_lookups()
            self._sort_countries()
            return
        index = await asyncio.to_thread(build_server_index, source)
        self.server_index = index
        apply_server_index(self.countries, index)
        self._rebuild_lookups()
        self._sort_countries()
        try:
            ORBIT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = ORBIT_INDEX_CACHE.with_suffix(".tmp")
            await asyncio.to_thread(
                tmp.write_text,
                json.dumps(index, separators=(",", ":")),
                "utf-8",
            )
            os.replace(tmp, ORBIT_INDEX_CACHE)
        except Exception:
            pass
        self._refresh_main()

    def resolve_country_code(self, value: str) -> str:
        if not value:
            return ""
        raw = value.strip()
        if len(raw) == 2:
            code = raw.upper()
            if code in self.countries:
                return code
            iso = PROTON_TO_ISO.get(code)
            if iso and iso in self.countries:
                return iso
        normalized = normalize_name(raw)
        code = self._name_lookup.get(normalized)
        if code:
            return code
        code = COUNTRY_ALIASES.get(normalized, "")
        if code and code in self.countries:
            return code
        return ""

    def country_for(self, value: str) -> Optional[Country]:
        code = self.resolve_country_code(value)
        return self.countries.get(code) if code else None

    def city_country(self, city_name: str) -> str:
        return self._city_lookup.get(normalize_name(city_name), "")

    # -------------------------------------------------------------- selection

    def ensure_initial_selection(self) -> None:
        if self.connection.connected and self.connection.country_code:
            self.selected_code = self.connection.country_code
            if self.connection.city and self.connection.country_code in self.countries:
                if self.connection.city in self.countries[self.connection.country_code].cities:
                    self.selected_city_name = self.connection.city
            return
        if self.selected_code in self.countries:
            return
        allowed = self.allowed_countries()
        candidates = [c for c in allowed if c.lat or c.lon]
        if not candidates:
            candidates = [c for c in self.country_list if c.lat or c.lon]
        if not candidates:
            return
        # Infer the home country so the default preview is an international
        # route rather than a zero-length loop inside the user's own country.
        if not self.home.country_code:
            nearest = min(
                candidates,
                key=lambda c: haversine_km(self.home.lat, self.home.lon, c.lat, c.lon),
            )
            if haversine_km(self.home.lat, self.home.lon, nearest.lat, nearest.lon) < 1200:
                self.home.country_code = nearest.code
        best: Optional[Country] = None
        best_score = 1e18
        for country in candidates:
            distance = haversine_km(self.home.lat, self.home.lon, country.lat, country.lon)
            if country.code == self.home.country_code:
                distance += 5000
            elif distance < 450:
                distance += 1200
            score = distance
            if not country.servers:
                score += 1500
            if score < best_score:
                best_score = score
                best = country
        if best is not None:
            self.selected_code = best.code
            self.selected_city_name = None

    def selected_country(self) -> Optional[Country]:
        if self.selected_code:
            return self.countries.get(self.selected_code)
        return None

    def select_country(self, code: str, city: Optional[str] = None) -> None:
        code = (code or "").upper()
        if code not in self.countries:
            return
        if code != self.selected_code:
            self.selected_city_name = None
        self.selected_code = code
        if city:
            self.selected_city_name = city
        elif city is None and code == self.selected_code and self.selected_city_name:
            # Selecting the same country from the map clears the city.
            if city is None:
                self.selected_city_name = None
        if self.main_screen is not None:
            self.main_screen.refresh_cards()
            self.main_screen.refresh_map_head()
            if self.main_screen.map is not None:
                self.main_screen.map.refresh()

    def clear_city(self) -> None:
        self.selected_city_name = None
        if self.main_screen is not None:
            self.main_screen.refresh_cards()
            if self.main_screen.map is not None:
                self.main_screen.map.refresh()

    def place_for_country(self, country: Country) -> dict[str, Any]:
        return {
            "label": country.name,
            "lat": country.lat,
            "lon": country.lon,
            "code": country.code,
            "city": "",
        }

    def selection_place(self) -> Optional[dict[str, Any]]:
        country = self.selected_country()
        if country is None:
            return None
        city_name = self.selected_city_name
        if city_name:
            city = country.cities.get(city_name)
            if city:
                return {
                    "label": city_name,
                    "lat": city.lat,
                    "lon": city.lon,
                    "code": country.code,
                    "city": city_name,
                }
        return self.place_for_country(country)

    def pending_target_place(self) -> Optional[dict[str, Any]]:
        if not self.pending:
            return None
        if self.pending.get("lat") is None or self.pending.get("lon") is None:
            return None
        return self.pending

    def connect_args_for_selection(self) -> tuple[list[str], Optional[dict[str, Any]]]:
        flags = self.feature_flags()
        country = self.selected_country()
        if country is not None and self.selected_city_name:
            args = ["connect", "--city", self.selected_city_name, *flags]
            return args, self.selection_place()
        if country is not None:
            args = ["connect", "--country", country.code, *flags]
            return args, self.place_for_country(country)
        return ["connect", *flags], None

    def feature_flags(self) -> list[str]:
        flags: list[str] = []
        if self.features.get("p2p"):
            flags.append("--p2p")
        if self.features.get("securecore"):
            flags.append("--securecore")
        if self.features.get("tor"):
            flags.append("--tor")
        if self.features.get("random"):
            flags.append("--random")
        return flags

    def allowed_countries(self) -> list[Country]:
        return [c for c in self.country_list if c.code not in self.excluded_codes]

    def set_excluded(self, code: str, excluded: bool) -> None:
        code = code.upper()
        if code not in self.countries:
            return
        if excluded:
            self.excluded_codes.add(code)
        else:
            self.excluded_codes.discard(code)
        if self.config["autoconnect"].get("preferred") == code and excluded:
            self.config["autoconnect"]["preferred"] = ""
        self.save_preferences()
        if self.main_screen is not None:
            self.main_screen.refresh_cards()
            if self.main_screen.map is not None:
                self.main_screen.map.refresh()

    def scan_candidates(self) -> list[Country]:
        allowed = [c for c in self.allowed_countries() if c.lat or c.lon]
        if not allowed:
            return []
        ranked = sorted(
            allowed,
            key=lambda c: (c.servers * (100 - min(99, c.load)) if c.servers else 1),
            reverse=True,
        )
        return ranked[:12]

    def autoconnect_target(self) -> Optional[Country]:
        allowed = [c for c in self.allowed_countries() if c.lat or c.lon]
        if not allowed:
            return None
        preferred = (self.config["autoconnect"].get("preferred") or "").upper()
        if preferred and preferred not in self.excluded_codes:
            country = self.countries.get(preferred)
            if country is not None:
                return country
        weights: list[float] = []
        for country in allowed:
            if country.servers:
                quality = max(0.25, (100 - min(99, country.load)) / 100.0)
                weight = country.servers * quality
            else:
                weight = 1.0
            # Give small networks a fair chance.
            weights.append(max(1.0, weight ** 0.65))
        try:
            return random.choices(allowed, weights=weights, k=1)[0]
        except Exception:
            return random.choice(allowed)

    # ------------------------------------------------------------------ source

    def set_home_timezone(self) -> None:
        self.home = timezone_home()
        self.config["source"] = {}
        try:
            save_config(self.config)
        except Exception:
            pass

    async def refine_home_via_ip(self) -> Optional[HomeLocation]:
        result = await asyncio.to_thread(fetch_ip_home)
        if result is None:
            return None
        self.home = result
        self.config["source"] = {
            "label": result.label,
            "lat": result.lat,
            "lon": result.lon,
            "country_code": result.country_code,
            "kind": result.kind,
            "updated": time.time(),
        }
        try:
            save_config(self.config)
        except Exception:
            pass
        if self.main_screen is not None:
            self.main_screen.refresh_all()
        return result

    # ----------------------------------------------------------------- helpers

    def update_map_meta(self, text: Optional[str]) -> None:
        if self.main_screen is not None:
            self.main_screen.update_map_meta(text)


def main() -> None:
    app = OrbitApp()
    app.run(mouse=True)


if __name__ == "__main__":
    main()

