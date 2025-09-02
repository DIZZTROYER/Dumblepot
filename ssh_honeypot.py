#Libraries
import logging
from logging.handlers import RotatingFileHandler
import socket
import paramiko
import threading
#Constants
logging_format = logging.Formatter('%(message)s')
SSH_BANNER = "SSH-2.0-MySSHServer_1.0"

#host_key = 'server.key'
host_key = paramiko.RSAKey(filename='server.key')

#Loggers & Logging Files
funnel_logger = logging.getLogger('FunnelLogger')
funnel_logger.setLevel(logging.INFO)
funnel_handler = RotatingFileHandler('audits.log', maxBytes=2500, backupCount=5 )
funnel_handler.setFormatter(logging_format)
funnel_logger.addHandler(funnel_handler)


creds_logger = logging.getLogger('CredsLogger')
creds_logger.setLevel(logging.INFO)
creds_handler = RotatingFileHandler('cmd_audits.log', maxBytes=2500, backupCount=5 )
creds_handler.setFormatter(logging_format)
creds_logger.addHandler(creds_handler)

#Emulated shell

class Node:
    def __init__(self, kind="dir", content=""):
        self.kind = kind              # "dir" or "file"
        self.children = {}            # name -> Node (for dirs)
        self.content = content        # str (for files)

class ShellState:
    def __init__(self):
        self.root = Node("dir")
        self.cwd = []  # current path parts, [] means "/"
        self._seed_world()

    def _seed_world(self):
        # Seed root with some magical files and places
        self.root.children["wand"]  = Node("file", "A holly wand with phoenix feather core.")
        self.root.children["cloak"] = Node("file", "A plain-looking cloak (or is it?).")
        self.root.children["map"]   = Node("file", "I solemnly swear that I am up to no good.")
        self.root.children["owl"]   = Node("file", "A snowy owl, faithfully waiting.")
        # Hidden artifact for ls -la
        self.root.children[".invisibility_cloak"] = Node("file", "Shh. You were not supposed to see this.")
        # A house directory
        self.root.children["gryffindor"] = Node("dir")
        self.root.children["gryffindor"].children["common_room"] = Node("dir")
        self.root.children["gryffindor"].children["portrait"] = Node("file", "The Fat Lady hums a tune.")

    def _get_dir(self, path_parts):
        node = self.root
        for part in path_parts:
            if part not in node.children:
                return None
            nxt = node.children[part]
            if nxt.kind != "dir":
                return None
            node = nxt
        return node

    def _get_node(self, path_parts):
        node = self.root
        for part in path_parts:
            if part not in node.children:
                return None
            node = node.children[part]
        return node
    
def emulated_shell(channel, client_ip):
    state = ShellState()
    channel.send(b'Dumbledore$ ')
    command = b""
    while True:
        char = channel.recv(1)
        channel.send(char)
        if not char:
            channel.close()
            break

        command += char
        if char == b'\r':
            if command.strip() == b'exit':
                response = b'\n Goodbye!\n'
                channel.close()
            elif command.strip() == b'pwd':
                response = b"\n" + b'\\usr\\local' + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'whoami':
                response = b"\n" + b"Harry Potter" + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'ls':
                node = state._get_node(state.cwd)
                if node and node.kind == "dir":
                    entries = []
                    for name, child in node.children.items():
                        if child.kind == "dir":
                            entries.append(f"{name}/")  
                        else:
                            entries.append(name)
                    if entries:
                        response = ("\n" + "  ".join(entries) + "\r\n").encode("utf-8")
                    else:
                        response = b"\nThe chamber echoes... it is empty.\r\n"
                else:
                    response = b"\nYou seem lost in the void...\r\n"
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip().startswith(b'cat'):
                parts = command.strip().split()
                if len(parts) > 1:
                    filename = parts[1].decode("utf-8", errors="ignore")
                    node = state._get_node(state.cwd + [filename])
                    if node is None:
                        response = f"\nNo such scroll or spellbook: {filename}\r\n".encode("utf-8")
                    elif node.kind != "file":
                        response = f"\n'{filename}' is not a scroll.\r\n".encode("utf-8")
                    else:
                        response = f"\n{node.content}\r\n".encode("utf-8")
                else:
                    response = b"\nWhisper the name of the scroll you seek.\r\n"
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip().startswith(b'cd'):
                parts = command.strip().split()
                if len(parts) > 1:
                    dirname = parts[1].decode("utf-8", errors="ignore")
                    if dirname == "/":
                        state.cwd = []  
                        response = b"\nYou return to the Great Hall (root).\r\n"
                    elif dirname == "..":
                        if state.cwd:
                            state.cwd.pop()
                            response = b"\nYou ascend to the previous chamber.\r\n"
                        else:
                            response = b"\nYou are already in the Great Hall.\r\n"
                    else:
                        node = state._get_node(state.cwd + [dirname])
                    if node and node.kind == "dir":
                        state.cwd.append(dirname)
                        response = f"\nYou enter the {dirname} chamber.\r\n".encode("utf-8")
                    elif node is None:
                        response = f"\nNo such chamber: {dirname}\r\n".encode("utf-8")
                    else:
                        response = f"\n'{dirname}' is a scroll, not a chamber.\r\n".encode("utf-8")
                else:
                    state.cwd = []
                    response = b"\nYou return to the Great Hall (root).\r\n"

            elif command.strip() == b'echo':
                response = b"\n" + b"Your voice echoes through the halls of Hogwarts." + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'clear':
                response = b"\n" + b"The Marauder's Map wipes itself clean." + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'ls -la':
                response = b"\n" + b". (You see footprints of mischievous students)\r\n.. (Filch lurking)\r\ncloak_of_invisibility\r\nwand_of_elder\r\nhorcruxes\r\n" + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'man':
                response = (
        b"\nAvailable Commands (Magical Edition):\r\n"
        b"  pwd        - Show your current location in the castle\r\n"
        b"  whoami     - Reveal your true wizarding identity\r\n"
        b"  ls         - List magical items in the chamber\r\n"
        b"  cat <file> - Read a spellbook or scroll\r\n"
        b"  cd         - Apparate to a different directory\r\n"
        b"  echo       - Make your voice echo in the halls\r\n"
        b"  clear      - Wipe the Marauder's Map clean\r\n"
        b"  ls -la     - Reveal hidden enchanted artifacts\r\n"
        b"  sudo       - Ask Dumbledore for special permissions\r\n"
        b"  rm -rf /   - A curse so strong it could end the wizarding world\r\n"
        b"  ps         - Show running spells and enchantments\r\n"
        b"  uname -a   - Display the Hogwarts kernel version\r\n"
        b"  netstat    - Show active Floo Network connections\r\n"
        b"  date       - Display the current date in wizarding history\r\n"
        b"  uptime     - See how long Hogwarts has been running\r\n"
        b"  fortune    - Receive wisdom from Dumbledore\r\n"
        b"  exit       - Leave the magical shell\r\n"
    )
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip().startswith(b'mkdir'):
                parts = command.strip().split()
                if len(parts) > 1:
                    dirname = parts[1].decode("utf-8", errors="ignore")
                    msg = "\nA new secret chamber named '{}' has been conjured.\r\n".format(dirname)
                    response = msg.encode("utf-8")
                else:
                    response = b"\nYou must specify the name of the chamber to conjure.\r\n"
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')    
            elif command.strip() == b'sudo':
                response = b"\n" + b"Dumbledore grants you special permissions." + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'rm -rf /':
                response = b"\n" + b"A curse this powerful could destroy the entire wizarding world!" + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'ps':
                response = b"\n" + b"123 Patronus_charm (running)\r\n456 Expelliarmus (sleeping)\r\n789 DarkMark (zombie)" + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'uname -a':
                response = b"\n" + b"Hogwarts Kernel 9.3.7 Owlery x86_64 (MagicOS)" + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'netstat':
                response = b"\n" + b"Connections:\r\nHogsmeade -- Port 9-3/4 -- ESTABLISHED\r\nMinistry_of_Magic -- Port 1997 -- LISTENING" + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'date':
                response = b"\n" + b"31 October 1981 - The night everything changed." + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'uptime':
                response = b"\n" + b"Server has been running since the Triwizard Tournament." + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            elif command.strip() == b'fortune':
                response = b"\n" + b'"It does not do to dwell on dreams and forget to live." - Dumbledore' + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')
            else:
                response = b"\n" + bytes(command.strip()) + b'\r\n'
                creds_logger.info(f'Command {command.strip()}' + 'executed by ' + f'{client_ip}')

            channel.send(response)
            channel.send(b'Dumbledore$ ')
            command = b""



    
#SSH Server + Sockets

class Server(paramiko.ServerInterface):

    def __init__(self, client_ip, input_username=None, input_password=None):
        self.event = threading.Event()
        self.client_ip = client_ip
        self.input_username = input_username
        self.input_password = input_password

    def check_channel_request(self, kind: str, chanid: int):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        
    def get_allowed_auths(self, username: str):
        return "password"
    
    def check_auth_password(self, username, password):
        funnel_logger.info(f'Client {self.client_ip} attempted connection with ' + f'username: {username}, ' + f'password: {password}')
        creds_logger.info(f'{self.client_ip}, {username}, {password}')
        if self.input_username is not None and self.input_password is not None:
           if username == self.input_username and password == self.input_password:
               return paramiko.AUTH_SUCCESSFUL
           else:
               return paramiko. AUTH_FAILED
        else:
           return paramiko.AUTH_SUCCESSFUL
       
    def check_channel_shell_request(self, channel):
        self.event.set()
        return True
    
    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True
    
    def check_channel_exec_request(self, channel, command):
        command = str(command)
        return True
    
def client_handle(client, addr, username, password):
    client_ip = addr[0]
    print(f"{client_ip} has connected to the server.")

    try:

        transport = paramiko.Transport(client)
        transport.local_version = SSH_BANNER
        server = Server(client_ip=client_ip, input_username=username, input_password=password)

        transport.add_server_key(host_key)

        transport.start_server(server=server)

        channel = transport.accept(100)
        if channel is None:
            print("No channel was opened.")

        standard_banner = "Welcome to My world, Dear Griffindor (HOCUS POCUS)!\r\n\r\n "
        channel.send(standard_banner)
        emulated_shell(channel, client_ip=client_ip)
    
    except Exception as error:
        print(error)
        print("!!! ERROR ENCOUNTERED WITH SPELL !!!")
        
    finally:
        try:
            transport.close()
        except Exception as error:
            print(error)
            print("!!! ERROR ENCOUNTERED WITH SPELL !!!")
        client.close()

#Provisons SSH based Honeypot

def honeypot(address, port, username, password):

    socks = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socks.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    socks.bind((address, port))

    socks.listen(100)
    print(f"SSH Server is listening on port {port}.")

    while True:
        try: 
            client, addr = socks.accept()
            ssh_honeyport_thread = threading.Thread(target=client_handle, args=(client, addr, username, password))
            ssh_honeyport_thread.start()
            pass
        except Exception as error:
            print(error)


honeypot('127.0.0.1', 2223, username=None, password=None)