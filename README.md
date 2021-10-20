# getnear – 

* Easily add VLANs to consumer grade ethernet switches
  * NetGear E-Series: supported!
  * NetGear T-Series: also supported!
* Accidentally disable important devices used by your whole family
* Put off important tasks by fiddling with your "home lab" instead

## Example

```Python
from getnear.switch import connect
from getnear.config import simple, Trunk, Unused

My_Stuff_Trusted = 12
Rostelecom_Trusted = 14
Huawei_Trusted = 15

connect('switch01.example.com').sync(simple(
    Trunk,              # port1: ^upstream
    Trunk,              # port2: switch02
    Unused,             # port3:
    Trunk,              # port4: switch03
    Trunk,              # port5: switch03
    Huawei_Trusted,     # port6: cat monitor: kitchen
    Rostelecom_Trusted, # port7: smart fridge
    Rostelecom_Trusted, # port8: cat monitor: guest bedroom
    ))

connect('switch02.example.com').sync(simple(
    Trunk,              # port1: ^upstream
    My_Stuff_Trusted,   # port2: Windows PC
    My_Stuff_Trusted,   # port3: Windows PC
    Unused,             # port4: 
    Rostelecom_Trusted, # port5: smart TV w/ microphone
    ))

# ...etc
```
