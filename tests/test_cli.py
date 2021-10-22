from getnear.cli import main

args = '''
    --hostname x --password y --
        port 1 trunk 12-15
        port 2 trunk 15
        port 3 access 3
        port 4 access 35
        port 5 trunk 2-7
'''

main(args.split())
