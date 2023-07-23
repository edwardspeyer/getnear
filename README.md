# getnear

```sh
# configure-vlans
python3 -m getnear        \
    "192.168.1.1"         \
    "pASSwORD"            \
    --trunk   1,12,15,17  \
    --access  1           \
    --access  1           \
    --trunk   1,15        \
    --access  17          \
    --access  1           \
    --access  1           \
    --access  12
```

```
$ ./configure-vlans
PORT    PVID  1    12    15    17
------  ------  ---  ----  ----  ----
     1       1  T    T     T     T
     2       1  A    ∙     ∙     ∙
     3       1  A    ∙     ∙     ∙
     4       1  T    ∙     T     ∙
     5      17  ∙    ∙     ∙     A
     6       1  A    ∙     ∙     ∙
     7       1  A    ∙     ∙     ∙
     8      12  ∙    A     ∙     ∙
set 802.1Q status False
set 802.1Q status True
add vlan   17
add vlan   12
add vlan   15
set vlan   17 members TTTTTTTT
set vlan   12 members TTTTTTTT
set vlan   15 members TTTTTTTT
set pvid    1 on ports {1, 2, 3, 4, 6, 7}
set pvid   17 on ports {5}
set pvid   12 on ports {8}
set pvid   15 on ports set()
set vlan    1 members TAAT-AA-
set vlan   17 members T---A---
set vlan   12 members T------A
set vlan   15 members T--T----
```
