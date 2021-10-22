# getnear

* Manage a wide variety of consumer grade ethernet switches, with ease!
  * NetGear E-Series: supported!
  * NetGear T-Series: also supported!
* Easily add new VLANs, configure port PVIDs, and curate VLAN membership
* Accidentally disable important devices used by your whole family
* Put off important tasks by fiddling with your "home lab" instead

## Example

```shell
$ getnear --hostname switch01.example.com \
> port 1 trunk 12,14,15 : upstream  \
> port 2 trunk 12,14,15 : switch02  \
> port 3 access 1       : unused    \
> port 4 trunk 12,14,15 : switch03  \
> port 5 trunk 12,14,15 : switch04  \
> port 6 access 15      : Huawei cat monitor \
> port 7 access 14      : Rostelecom smart fridge \
> port 8 access 14      : Rostelecom cat monitor
switch01.example.com:

      PORT    PVID  1    12    14    15
    ------  ------  ---  ----  ----  ----
         1       1  U    T     T     T
         2       1  U    T     T     T
         3       1  U    _     _     _
         4       1  U    T     T     T
         5       1  U    T     T     T
         6      15  _    _     _     U
         7      14  _    _     U     _
         8      14  _    _     U     _
use --commit to commit changes
```
