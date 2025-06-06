import re
import time
from typing import Optional
import paramiko

class SSHOutputHandler:
    """Handles SSH output processing with improved encoding detection and buffering."""
    ENCODINGS = ['utf-8', 'latin-1', 'cp1252', 'ascii']
    BUFFER_SIZE = 8192

    @staticmethod
    def decode_output(data: bytes) -> str:
        """Attempts to decode byte data using multiple encodings."""
        for encoding in SSHOutputHandler.ENCODINGS:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode('utf-8', errors='replace')

    @staticmethod
    def receive_data(shell: paramiko.Channel, timeout: float, is_interactive: bool = False, is_command_shell: bool = False) -> str:
        """Receives data from shell with efficient command completion detection."""
        start_time = time.time()
        out = ""
        in_msfconsole = False
        last_output_time = start_time
        idle_threshold = 2.0  # Reduced for fast command shell commands

        while True:
            if shell.recv_ready():
                data = shell.recv(SSHOutputHandler.BUFFER_SIZE)
                decoded_data = SSHOutputHandler.decode_output(data)
                out += decoded_data
                last_output_time = time.time()

                # Check for Metasploit prompt
                if 'msf6 >' in out.lower():
                    in_msfconsole = True
                    if is_interactive:
                        break

                # In command shell, stop when output stabilizes
                if is_command_shell:
                    if time.time() - last_output_time > idle_threshold:
                        break
                    if time.time() - start_time > timeout:
                        print(f"Timeout waiting for output after {timeout} seconds in command shell session")
                        break
                    time.sleep(0.01)  # Faster polling for command shell
                    continue

            # In Metasploit, stop when output stabilizes
            if in_msfconsole:
                if time.time() - last_output_time > idle_threshold:
                    break
                if time.time() - start_time > timeout:
                    print(f"Timeout waiting for output after {timeout} seconds in Metasploit session")
                    break
                time.sleep(0.02)
                continue

            # Non-command-shell: check for prompt
            lines = out.split('\n')
            lines = [x.strip() for x in lines if x.strip()]
            if len(lines) > 0:
                last_line = lines[-1].strip()
                if ('@' in last_line and (last_line[-1] in '$#')) or \
                        ('bash' in last_line and (last_line[-1] in '$#')) or \
                        last_line[-1] in ['?', '$', '#'] or \
                        '--more--' in last_line.lower() or \
                        last_line[-1] == ':' and '::' not in last_line and '-->' not in last_line or \
                        last_line[-1] == '>' and '<' not in last_line and '-->' not in last_line:
                    break

            # Timeout for non-command-shell
            if time.time() - start_time > timeout:
                print(f"Timeout after {timeout} seconds")
                if not (is_command_shell or in_msfconsole):
                    shell.send('\x03')
                    time.sleep(0.5)
                    out += SSHOutputHandler.decode_output(shell.recv(SSHOutputHandler.BUFFER_SIZE))
                break

            time.sleep(0.01)

        return out

class RemoteShell:
    """Enhanced remote shell handler with efficient command execution."""
    FORBIDDEN_COMMANDS = {'apt', 'apt-get', 'sudo'}

    def __init__(self, shell: paramiko.Channel, timeout: float = 120.0):
        self.shell = shell
        self._setup_shell(timeout)

    def _setup_shell(self, timeout: float) -> None:
        """Initializes shell settings."""
        try:
            self.shell.settimeout(timeout)
            self.shell.set_combine_stderr(True)
            self.execute_cmd("touch ~/.hushlogin")
            motd_commands = [
                "touch /etc/legal",
                "chmod 644 /etc/legal",
                "rm -f /etc/motd",
                "rm -f /etc/update-motd.d/*"
            ]
            for cmd in motd_commands:
                self.execute_cmd(cmd)
        except Exception as e:
            print(f"Shell setup warning: {e}")

    def _check_forbidden_commands(self, cmd: str) -> Optional[str]:
        """Validates command against forbidden commands list."""
        cmd_parts = cmd.split()
        if any(cmd in self.FORBIDDEN_COMMANDS for cmd in cmd_parts):
            return f"Command not allowed: {cmd} is restricted in minimal shell"
        return None

    def execute_cmd(self, cmd: str) -> str:
        """Executes command with efficient output handling."""
        if error_msg := self._check_forbidden_commands(cmd):
            return error_msg

        self.shell.send(cmd + '\n')
        time.sleep(0.05)
        output = []

        # Set timeout based on command type
        is_interactive = any(kw in cmd.lower() for kw in ['msfconsole', 'use ', 'info ', 'search ', 'set ', 'exploit'])
        is_command_shell = any(kw in cmd.lower() for kw in ['cat ', 'id ', 'ls ', 'whoami', 'cd ']) or 'command shell session' in cmd.lower()
        cmd_timeout = 60.0 if any(kw in cmd.lower() for kw in ['nmap', 'find', 'exploit', 'run']) else 10.0
        if is_interactive:
            cmd_timeout = 60.0
        if is_command_shell:
            cmd_timeout = 10.0  # Short timeout for command shell

        data = SSHOutputHandler.receive_data(self.shell, timeout=cmd_timeout, is_interactive=is_interactive, is_command_shell=is_command_shell)
        if data:
            output.append(data)

        return ''.join(output)

def clean_dirb_output(output):
    """Clean the output from the 'dirb' command."""
    output = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', output)
    summary_pattern = r"(URL_BASE:.*\n|WORDLIST_FILES:.*\n|GENERATED WORDS:.*\n|---- Scanning URL:.*\n)"
    summary = "\n".join(re.findall(summary_pattern, output))
    url_pattern = r"http[^\s]+ \(CODE:[0-9]+\|SIZE:[0-9]+\)"
    urls = "\n".join(re.findall(url_pattern, output))
    stats_pattern = r"DOWNLOADED: \d+ - FOUND: \d+"
    stats = "\n".join(re.findall(stats_pattern, output))
    return f"{summary}\n{urls}\n{stats}"

def clean_msfconsole_output(output):
    """Clean the output from the 'msfconsole' command."""
    output = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', output)
    cleaned = [line for line in output.splitlines() if
               not any(x in line.lower() for x in ["loading", "warning:", "starting", "====="])]
    relevant_output = []
    for line in cleaned:
        if line.strip() and any(keyword in line.lower() for keyword in ['metasploit', 'exploits', 'payloads', ' >', '-', '+']):
            relevant_output.append(line.strip())
    return "\n".join(relevant_output)
