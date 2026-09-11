import argparse, json
from yum_cli import list_installed_packages, get_package_info

def main():
    parser = argparse.ArgumentParser(description='Simple YUM helper commands')
    parser.add_argument('--list', action='store_true', help='List installed packages as JSON')
    parser.add_argument('--info', type=str, help='Get detailed info for a package')
    args = parser.parse_args()
    if args.list:
        print(json.dumps(list_installed_packages(), indent=2))
    elif args.info:
        print(json.dumps(get_package_info(args.info), indent=2))
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
