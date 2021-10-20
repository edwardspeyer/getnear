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
    Trunk,              # ^upstream
    Trunk,              # switch02
    Unused,
    Trunk,              # switch03
    Trunk,              # switch03
    Huawei_Trusted,     # cat monitor: kitchen
    Rostelecom_Trusted, # smart fridge
    Rostelecom_Trusted, # cat monitor: guest bedroom
    ))

connect('switch02.example.com').sync(simple(
    Trunk,              # ^upstream
    My_Stuff_Trusted,   # Windows PC
    My_Stuff_Trusted,   # Windows PC
    Unused,
    Rostelecom_Trusted, # smart TV w/ microphone
    ))

# ...etc
```
