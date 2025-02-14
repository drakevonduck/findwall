import argparse
import getpass
from colorama import Fore, Back, Style
from tqdm import tqdm
import threading
import paramiko
import time
import socket

MAX_THREADS = 5
TCP_TIMEOUT = 60
BANNER_TIMEOUT = 60
AUTH_TIMEOUT = 60

BLOCKED_PORTS = []

def show_blocked_ports(udp):
    if udp:
        message = f"Blocked UDP ports: {str(sorted(BLOCKED_PORTS))}"
    else:
        message = f"Blocked TCP ports: {str(sorted(BLOCKED_PORTS))}"
    error(message)


def open_remote_port(session, port_to_scan, udp):
    command = f"echo test | nc -nlp {str(port_to_scan)}"
    if udp:
        command = f"{command} -u"
    command = f"{command} > /dev/null 2>&1 &"
    stdin, stdout, stderr = session.exec_command(command)
    time.sleep(2)


def check_remote_port(session, ssh_host, port_to_scan, udp):
    try:
        if udp:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.sendto(bytes("test", "utf-8"), (ssh_host, port_to_scan))
            data, addr = s.recvfrom(1024)
        else: 
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((ssh_host, port_to_scan))
    except Exception as err:
        BLOCKED_PORTS.append(port_to_scan)
    finally:
        s.close()
        stdin, stdout, stderr = session.exec_command(f"kill -9 $(lsof -t -i:{str(port_to_scan)})")


def close_session(session):
	session.close()


def open_session(ssh_host, ssh_port, ssh_username, ssh_password, ssh_key):
    session = paramiko.SSHClient()
    session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if ssh_key:
            session.connect(ssh_host, port=ssh_port, username=ssh_username, password=ssh_password, key_filename=ssh_key, timeout=TCP_TIMEOUT, banner_timeout=BANNER_TIMEOUT, auth_timeout=AUTH_TIMEOUT)
        else:
            session.connect(ssh_host, port=ssh_port, username=ssh_username, password=ssh_password, timeout=TCP_TIMEOUT, banner_timeout=BANNER_TIMEOUT, auth_timeout=AUTH_TIMEOUT)
    except Exception as err:
        error(str(err))
        exit(1)
    return session


def check_blocked_port(ssh_host, ssh_port, ssh_username, ssh_password, ssh_key, port_to_scan, udp):
    if ssh_port == port_to_scan:
        return
    session = open_session(ssh_host, ssh_port, ssh_username, ssh_password, ssh_key)
    open_remote_port(session, port_to_scan, udp)
    check_remote_port(session, ssh_host, port_to_scan, udp)
    close_session(session)


def setup_remote_host(ssh_host, ssh_port, ssh_username, ssh_password, ssh_key):
    session = open_session(ssh_host, ssh_port, ssh_username, ssh_password, ssh_key)
    # Check if nc is already installed
    stdin, stdout, stderr = session.exec_command("which nc")
    if not stdout.readlines():
        # Automatically install nc
        stdin, stdout, stderr = session.exec_command("apt update; apt install nc")
        if stderr.readlines():
            # Impossible to install nc
            error("You don't have privileges to install nc on remote host.")
            warning("Install it manually via root account.")
            exit(1)
    session.close()


def parse_port_range(ports):
    # https://stackoverflow.com/questions/712460/interpreting-number-ranges-in-python
    selection = set()
    invalid = set()
    # tokens are comma seperated values
    tokens = [x.strip() for x in ports.split(',')]
    for i in tokens:
        if len(i) > 0 and i[:1] == "<":
            i = f"1-{i[1:]}"
        try:
            # typically tokens are plain old integers
            selection.add(int(i))
        except Exception:
            # if not, then it might be a range
            try:
                token = [int(k.strip()) for k in i.split('-')]
                if len(token) > 1:
                    token.sort()
                    # we have items seperated by a dash
                    # try to build a valid range
                    first = token[0]
                    last = token[-1]
                    for x in range(first, last+1):
                        selection.add(x)
            except Exception:
                # not an int and not a range...
                invalid.add(i)
    # Report invalid tokens before returning valid selection
    if invalid:
        print(f"Invalid set: {invalid}")
    return sorted(selection)


def info(message):
    print(f'[+] {message}')


def warning(message):
    print(f'{Fore.YELLOW}[*] {message}')
    print(Style.RESET_ALL)


def error(message):
    print(f'{Fore.RED}[!] {message}')
    print(Style.RESET_ALL)


def print_banner():
    print("=====================================================================================")
    print(Style.RESET_ALL)
    print("\t" + Fore.GREEN + "███████╗██╗███╗   ██╗██████╗ " + Fore.RED + "██╗    ██╗ █████╗ ██╗     ██╗     ")
    print("\t" + Fore.GREEN + "██╔════╝██║████╗  ██║██╔══██╗" + Fore.RED + "██║    ██║██╔══██╗██║     ██║     ")
    print("\t" + Fore.GREEN + "█████╗  ██║██╔██╗ ██║██║  ██║" + Fore.RED + "██║ █╗ ██║███████║██║     ██║     ")
    print("\t" + Fore.GREEN + "██╔══╝  ██║██║╚██╗██║██║  ██║" + Fore.RED + "██║███╗██║██╔══██║██║     ██║     ")
    print("\t" + Fore.GREEN + "██║     ██║██║ ╚████║██████╔╝" + Fore.RED + "╚███╔███╔╝██║  ██║███████╗███████╗")
    print("\t" + Fore.GREEN + "╚═╝     ╚═╝╚═╝  ╚═══╝╚═════╝ " + Fore.RED + " ╚══╝╚══╝ ╚═╝  ╚═╝╚══════╝╚══════╝")
    print(Style.RESET_ALL)
    print("=====================================================================================")     
    print()


def main():
    # Banner
    print_banner()

    # Command-line parameters
    parser = argparse.ArgumentParser(description ='Check if someone is blocking you!')
    parser.add_argument('--ssh-host', required=True, dest='ssh_host', help='Remote host')
    parser.add_argument('--ssh-port', default=22, type=int, dest='ssh_port', help='Remote SSH port')
    parser.add_argument('--ssh-username', required=True, dest='ssh_username', help='Remote SSH username')
    parser.add_argument('--ssh-password', default="", dest='ssh_password', help='Remote SSH password')
    parser.add_argument('--ask-ssh-pass', dest='ask_ssh_pass', action='store_true', help='Ask for remote SSH password')
    parser.add_argument('--ssh-key', default="", dest='ssh_key', help='Remote SSH private key')
    parser.add_argument('--ports', required=True, default="1-1024", dest='ports', help='Port range to scan (default: 1-1024)')
    parser.add_argument('--udp', dest='udp', action='store_true', help='Scan in UDP')
    parser.add_argument('--threads', dest='threads', type=int, default=1, help='Number of threads (default: 1)')
    args = parser.parse_args()

    ssh_host = args.ssh_host
    ssh_port = args.ssh_port
    ssh_username = args.ssh_username
    ssh_password = args.ssh_password
    ask_ssh_pass = args.ask_ssh_pass
    ssh_key = args.ssh_key
    ports = args.ports
    udp = args.udp
    threads = args.threads

    if threads > MAX_THREADS:
        error("The max number of threads is " + MAX_THREADS)
        exit(1)

    if not ask_ssh_pass and not ssh_password and not ssh_key:
        error("Specify a password or a key file for the remote SSH host")
        exit(1)
        
    if ask_ssh_pass:
        ssh_password = getpass.getpass(prompt = 'Enter the SSH password')

    # Port range parsing
    ports = parse_port_range(args.ports)

    # Remote host setup
    info("Remote host setup started")
    setup_remote_host(ssh_host, ssh_port, ssh_username, ssh_password, ssh_key)
    info("Remote host setup completed")

    # Semaphore instantiation
    lock = threading.BoundedSemaphore(value=threads)

    # Blocked ports scanning
    info("Blocked ports scan started")
    threads = []
    for port_to_scan in tqdm(ports, desc="Scanning..."):
        lock.acquire()
        th = threading.Thread(target=check_blocked_port, args=(ssh_host, ssh_port, ssh_username, ssh_password, ssh_key, port_to_scan, udp))
        th.start()
        threads.append(th)
        time.sleep(1)
        lock.release()

    info("Blocked ports scan completed")

    # Results
    for th in threads:
        th.join()
    show_blocked_ports(udp)

if __name__ == "__main__":
    main()
