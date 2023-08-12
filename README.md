# getnear

- Manage a wide variety of commodity ethernet switches, with ease!
  - NetGear E-Series: supported!
  - NetGear T-Series: no longer supported!
- Easily add new VLANs, configure port PVIDs, and curate VLAN membership!
- Accidentally disable access to devices used by your family!
- Quickly re-enable access to devices used by your family!
- Put off important tasks by fiddling with your homelab instead!

```python
# example.py
from getnear import A, T, sync_ports

sync_ports(
    "192.168.1.124",
    "parsewort",
    [
        {1: A},
        {1: A, 12: T, 14: T},
        {1: A},
        {1: A},
        {12: A},
        {13: A},
        {14: A},
        {1: T, 12: T, 13: T, 14: T},
    ],
)
```

```sh
$ python3 ./example.py
Already logged in with a valid cookie
set 802.1Q status False
set 802.1Q status True
add vlan   12
add vlan   13
add vlan   14
set vlan    1 members TTTTTTTT
set vlan   12 members TTTTTTTT
set vlan   13 members TTTTTTTT
set vlan   14 members TTTTTTTT
set pvid    1 on port 1
set pvid    1 on port 2
set pvid    1 on port 3
set pvid    1 on port 4
set pvid   12 on port 5
set pvid   13 on port 6
set pvid   14 on port 7
set pvid    1 on port 8
set vlan    1 members AAAA∙∙∙T
set vlan   12 members ∙T∙∙A∙∙T
set vlan   13 members ∙∙∙∙∙A∙T
set vlan   14 members ∙T∙∙∙∙AT
```
