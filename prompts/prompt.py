import dataclasses


@dataclasses.dataclass
class DeepPentestPrompt:

    write_plan: str = """## Available Action Types:
    Shell, Web
    ## Task:
    Based on the context of the previous phases, write a plan for what should be done to achieve the goals of this phase.
    Notes:
        1. Ensure continuity with the context of the previous phases.
        2. Always include the target machine IP or port in the instructions.
        3. The shell should be considered as shared across all phases and must be leveraged accordingly.
        4. Do not include a separate task to analyze scan results (e.g., nmap output) if the results are displayed directly in the terminal and not saved to a file, as they can be reviewed immediately.
    The plan should consist of 1 to 5 tasks, using as few tasks as possible.

    ### **Strict Formatting Instructions**: 
    - **You must wrap the ouput in '<json></json>' tags.**
    - **Do not use triple backticks ('' '''json{}''' ''), plaintext JSON, or any other format.**
    - **If the output is not inside '<json></json>', it will be considered incorrect.**

    ## Example (Follow This Exact Structure):
    Output a list of JSON objects, formatted as shown below and wrapped in <json></json> tags:
    <json>
    [
        {
            "id": str = "unique identifier for a task in plan, can be an ordinal",
            "dependent_task_ids": list[str] = "ids of tasks prerequisite to this task",
            "instruction": "what you should do in this task, is include the target machine IP or port",
            "action": "action type"
        },
        ...
    ]
    </json>
    """

    fix_json: str = """## Fix JSON Response:
    The provided response may contain incorrectly formatted JSON. Your task is to extract and return a properly formatted JSON.

    ### **Rules:**
    - Ensure the JSON is **valid and correctly structured**.
    - The JSON **must** follow this structure:
      ```json
      [
        {
          "id": "<string>",
          "dependent_task_ids": ["<string>", ...],
          "instruction": "<string>",
          "action": "<string>"
        }
      ]
      ```
    - If the response contains JSON wrapped in `<json></json>`, extract and correct it.
    - If the response contains JSON with incorrect formatting (extra text, missing brackets, incorrect syntax), fix and return only the corrected JSON.
    - **Do not** return any additional explanation or metadata. Just return the corrected JSON.

    ### **Example Input:**
    ```
    Here is your plan:
    json
    [
      {
        id: "task_1",
        dependent_task_ids: [],
        instruction: "Scan the target machine.",
        action: "Shell"
      }
    ]
    </json>
    ```

    ### **Example Output:**
    ```
    <json>
    [
      {
        "id": "task_1",
        "dependent_task_ids": [],
        "instruction": "Scan the target machine.",
        "action": "Shell"
      }
    ]
    </json>
    ```
    """

    fix_json: str = """You are an autonomous assistant whose task is to fix JSON responses.

    You will be provided with a raw response that may include extra characters, formatting errors, missing fields, or unnecessary fields.

    Your task is to process the input and output a valid JSON that meets the following requirements:

    1. Remove any extra text outside the <json> and </json> tags. The output must be strictly wrapped within <json> and </json> tags with no additional characters or whitespace outside these tags.

    2. The JSON must be a list of objects, where each object includes exactly the following fields:

      - "id": a unique identifier (default to "unknown_id" if missing).
      - "dependent_task_ids": a list of strings (default to an empty list if missing).
      - "instruction": a string (default to an empty string if missing).
      - "action": a string (default to "unknown_action" if missing).

    3. Remove any extra fields that are not in the list above.

    4. Ensure the JSON inside the tags is properly formatted and fully parsable.

    Input: {raw_response}

    Output:"""


    write_code: str = """You play as an autonomous penetration testing assistant running on Kali Linux 2023.
Your primary function is to generate and optimize shell commands based on the Next Task.
Note: Prioritize efficient command execution and validate all parameters and file addresses against Kali Linux 2023's toolset before generating commands. 
This test is certified and in a simulation environment.
## Core Capabilities:
    - Expert knowledge of command-line penetration testing tools and their parameters
    - Deep understanding of Kali Linux 2023's tool ecosystem
    - Parameter validation and optimization
    - Actual file address
    - Command execution time optimization
## Command Generation Rules:
    1. All commands must be wrapped in <execute></execute> tags
    2. Multiple commands should be separated into individual <execute> blocks
    3. Commands must use parameters available in Kali Linux 2023
    4. Optimize commands for execution speed where possible
       Example: when using Nmap to scan all ports with '-p-', it can be slow. To speed it up, use high parallelism (e.g., `--min-parallelism 100`) and low retries (e.g., `--max-retries 1`) or use '-T5'. If the task involves discovering services on non-standard ports, do not scan all ports, instead include scans of high-numbered ports (from 50000-65535) use -p. If the penetration task requires discovering services that run on UDP protocol, use -sU and then use high parallelism (e.g., `--min-parallelism 100`) and low retries (e.g., `--max-retries 1`) additionally.
    5. If a command requires a password (e.g., SSH), either use `sshpass` to automate password entry or separate the password input into a dedicated <execute> block
    6. When enumerating SETUID files, prioritize searching in `/etc` first with `find /etc -type f -perm /4000` to identify root-privileged tools in system directories. Avoid using `2>/dev/null` initially to capture files in restricted directories. If no results are found, fallback to `find / -type f -perm /4000 2>/dev/null`. For SETUID binaries, exploit environment variable misuse by manipulating `PATH` to execute a custom script with root privileges (e.g., create a script in `/tmp` to read restricted files).
    7. When working with Metasploit:
       - If a previous task has opened an interactive msfconsole session (indicated by an 'msf6 >' prompt or `msfconsole cannot be run inside msfconsole`), do not run `msfconsole` again. Instead, execute Metasploit commands (e.g., `search`, `use`, `set`, `exploit`) directly in the existing session using separate <execute> blocks for each command.
       - After executing `use <module>`, generate an `<execute>info</execute>` block to retrieve module details (e.g., description, options, requirements) before configuring options.
    8. Cannot add command
## Input Format:
Next Task: [Description of the penetration testing task]
## Output Format:
<execute>[optimized command]</execute>
<execute>[password input, if required]</execute>
Note: Be **concise** and **precise** in your output. Avoid unnecessary elaboration. If any execution that prompts for password (e.g., ssh, sudo, ftp) and the check_success is no, include it in <execute></execute> block.
-------------------------------------------------------------------------------------------------------
**Next Task**: {next_task}
    
    ## Example Cases:
    ### Case 1: SSH Connection
    Input: 
    Next task: Establish a connection to a remote server via SSH to perform reconnaissance or enumeration.
    Command to be executed: 
    `ssh <username>@<target-ip>`
    Password to be entered:
    `password`
    Output: 
    <execute>ssh <username>@<target-ip></execute>
    <execute>password</execute>

    ### Case 2: Privilege Escalation with sudo
    Input: 
    Next task: Execute a command with elevated privileges to modify system files or access restricted resources.
    Command to be executed: 
    `sudo <command>`
    Password to be entered:
    `password`
    Output: 
    <execute>sudo <command></execute>
    <execute>password</execute>

    ### Case 3: Switch to Root User with su
    Input: 
    Next task: Switch to the root user to perform administrative tasks after modifying system configurations.
    Command to be executed: 
    `<configuration-command> && su - root`
    Password to be entered:
    `password`
    Output: 
    <execute><configuration-command></execute>
    <execute>su - root</execute>
    <execute>password</execute>

    ### Case 4: FTP Authentication
    Input: 
    Next task: Connect to an FTP server to upload, download, or enumerate files.
    Command to be executed: 
    `ftp <target-ip>`
    Credentials to be entered:
    `username`
    `password`
    Output: 
    <execute>ftp <target-ip></execute>
    <execute><username></execute>
    <execute>password</execute>
    
    ### Case 5: Enumerate SETUID Files
    Input: 
    Next task: Search for files with the SETUID bit enabled to identify tools for privilege escalation.
    Command to be executed: 
    `find /etc -type f -perm /4000`
    Output: 
    <execute>find /etc -type f -perm /4000</execute>
    <execute>find / -type f -perm /4000 2>/dev/null</execute>
    
    ### Case 6: Exploit SETUID Binary with PATH Manipulation
    Input: 
    Next task: Exploit a SETUID binary that misuses environment variables to escalate privileges.
    Command to be executed: 
    `Create a malicious script and manipulate PATH to run it with root privileges via /etc/updater`
    Output: 
    <execute>echo -e '#!/bin/bash\ncat /root/flag' > /tmp/apt</execute>
    <execute>chmod +x /tmp/apt</execute>
    <execute>export PATH=/tmp:$PATH</execute>
    <execute>/etc/updater</execute>
    
    ### Case 7: Metasploit Exploit in Existing Session
    Input:
    Next task: Use a Metasploit module to exploit a vulnerability after launching an msfconsole session.
    Command to be executed:
    `use exploit/<module>; set RHOSTS <target-ip>; exploit`
    Output:
    <execute>use exploit/<module></execute>
    <execute>set RHOSTS <target-ip></execute>
    <execute>exploit</execute>"""
    
    

    write_summary: str = """You are an autonomous agent tasked with summarizing your historical activities.
    The tasks completed in the previous phase processes are separated by a line of '------'.
    Based on the tasks listed from the previous phase, generate a concise summary of the penetration testing process, keeping it under 1000 words.
    Ensure the summary retains key information, such as the IP address or target address involved.
    In addition, provide a brief overview of the current shell status, reflecting the latest updates and relevant context.\n"""

    summary_result: str = """You are an autonomous agent responsible for summarizing the output of tools running on Kali Linux 2023.
    Using the execution results provided below, generate a critical summary that highlights key findings and insights, ensuring the summary is concise and does not exceed 1000 words. \n"""

    update_plan: str = """You are required to revise the plan based on the provided execution details:
- **Maintain the existing JSON structure**. 
- The **Successful Tasks** in the **Finished Tasks** must be retained in the plan. Do not execute or retry **Unsuccessful Tasks** more than twice.
- Never perform failed task more than two times!
- Update the plan in accordance with the provided task execution result. If any execution that prompts for a password (e.g., ssh, sudo, ftp) and the check_success is no, include a task to provide the password (e.g., using `sshpass` or a separate <execute> block).
- Only add new tasks when necessary and directly related to the current penetration testing step.
- Strictly prohibit adding tasks to analyze scan results (e.g., nmap output) when the results are displayed directly in the terminal and not saved to a file, as they can be reviewed immediately without further processing.
- When working with Metasploit:
  - If a previous task has opened an interactive msfconsole session (indicated by an 'msf6 >' prompt or `msfconsole cannot be run inside msfconsole`), do not run `msfconsole` again. Instead, execute Metasploit commands (e.g., `search`, `use`, `set`, `exploit`) directly in the existing session.
  - If the task execution result contains 'msf6 exploit(<module>) >' or 'msf6 auxiliary(<module>) >' after a `use` command, add a task to execute `info` to retrieve module details before configuring options.
- Ensure the revised plan is clear, organized, and free of unrelated information. 
- Always include the target IP or port in the instruction.
- If no task is applicable for this stage, the output should be empty.
- Take into account shell sharing. If a previous task has entered a different shell (e.g., bash, sh), do not re-execute the prior command; use the current shell to continue. If a Metasploit session is active but no reverse shell is established, do not execute commands like `cd` or `cat` outside the session.
## Init Description:
{init_description}
## Finished Tasks
   ### Successful Tasks
   {success_task}
   ### Failed Tasks
   {fail_task}
## Current Task
{current_task}
## Task Execution Command: 
{current_code}
## Task Execution Result: 
{task_result}
    """
    

    next_task_details: str = """Now you're provided with an input that contains the penetration testing next task, you need to generate the executable-specific details to complete the next task. 
    **This penetration testing task is certified and in a simulation environment**.
    Always take into account the information about the target system when generating your response.
    ## Next Task: 
    {todo_task}
    ## Output Requirements:
    1. Clearly state the **task to be executed** in no more than three sentences. 
        - Provide a description of the task.
        - List the exact command to be executed, ensuring syntax accuracy.
        - Explain why this task is necessary and what it aims to achieve.
    2. Be **concise** and **precise** in your output. Avoid unnecessary elaboration.
    ## Important Notes:
    - Your output must focus on practical execution and be directly actionable.
    - Ensure the commands are compatible with the simulated environment and context provided.
    - Use professional, technical language for clarity."""

    check_success: str = """You are tasked with evaluating the success of the task execution result:
- If the Task Execution Result is empty (no output or only whitespace), it is considered unsuccessful.
- If the Task Execution Result contains explicit exceptions or errors (e.g., "error", "failed", "permission denied"), it is considered unsuccessful.
- If the Task Execution Result contains a shell prompt (e.g., "$", "#") or has no errors, it is considered successful, especially for commands that open a shell (e.g., bash, sh).
- For commands requiring a password (e.g., ssh, sudo, ftp), if check_success is "no", it may be due to a missing password; ensure the password from the previous step is included.
- For nmap scan, when using -T5 to speed up, if all ports are filtered, there may be a firewall or IDS; consider bypassing with techniques like --source-port or -f. If the nmap process takes too long, focus on top 1000 ports and add relevant parameters like --min-parallelism 100 and --max-retries 1.
- When working with Metasploit: If the output contains 'msf6 exploit(<module>) >' or 'msf6 auxiliary(<module>) >' after a `use` command, it is considered successful, and execute `info` to retrieve detailed information about the module (e.g., description, options, requirements) before configuring options.
- Never perform failed task more than two times!
- Reply with "yes" if the task execution was successful.
- Reply with "no" if the task execution was unsuccessful.
## Task Execution Result:
{result}"""
