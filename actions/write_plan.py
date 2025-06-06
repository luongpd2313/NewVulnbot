import json
import re
from typing import List, Dict

from pydantic import BaseModel

from config.config import Configs
from prompts.prompt import DeepPentestPrompt
from db.models.plan_model import Plan
from db.models.task_model import TaskModel, Task
from server.chat.chat import _chat


import json
from typing import List, Dict, Any

def extract_plan_data(response: str) -> List[Dict[str, Any]]:
    """
    Trích xuất dữ liệu kế hoạch từ response của LLM, bất kể format.
    Args:
        response: Chuỗi response từ LLM
    Returns:
        Danh sách các dictionary chứa các trường cần thiết
    """
    required_fields = {"id", "dependent_task_ids", "instruction", "action"}
    extracted_plans = []

    # Loại bỏ các ký tự không mong muốn ở đầu và cuối
    cleaned_response = response.strip()

    # Thử tìm và trích xuất JSON từ các định dạng phổ biến
    try:
        # Xử lý các trường hợp JSON được bao quanh bởi các tag
        if "<json>" in cleaned_response and "</json>" in cleaned_response:
            json_str = cleaned_response.split("<json>")[1].split("</json>")[0]
        elif "```json" in cleaned_response and "```" in cleaned_response:
            json_str = cleaned_response.split("```json")[1].split("```")[0]
        elif "'''json" in cleaned_response and "'''" in cleaned_response:
            json_str = cleaned_response.split("'''json")[1].split("'''")[0]
        else:
            json_str = cleaned_response  # Giả sử toàn bộ response là JSON

        # Parse JSON
        parsed_data = json.loads(json_str.strip())

        # Chuẩn hóa dữ liệu thành danh sách các plan (nếu là dict đơn lẻ thì bọc trong list)
        if isinstance(parsed_data, dict):
            plans = [parsed_data]
        elif isinstance(parsed_data, list):
            plans = parsed_data
        else:
            raise ValueError("Parsed data is neither a dict nor a list")

        # Trích xuất các trường cần thiết
        for plan in plans:
            extracted_plan = {}
            for field in required_fields:
                extracted_plan[field] = plan.get(field, None)
                # Đảm bảo các giá trị mặc định hợp lý nếu field bị thiếu
                if extracted_plan[field] is None:
                    if field == "dependent_task_ids":
                        extracted_plan[field] = []
                    elif field == "id":
                        extracted_plan[field] = "unknown_id"
                    elif field == "instruction":
                        extracted_plan[field] = ""
                    elif field == "action":
                        extracted_plan[field] = "unknown_action"
            extracted_plans.append(extracted_plan)

    except (json.JSONDecodeError, IndexError, ValueError) as e:
        print(f"Error parsing response: {e}")
        # Trả về một plan mặc định nếu không parse được
        extracted_plans.append({
            "id": "error_id",
            "dependent_task_ids": [],
            "instruction": "Failed to parse response",
            "action": "error"
        })

    return extracted_plans

# class WritePlan(BaseModel):
#     plan_chat_id: str
#     def run(self, init_description) -> str:
#         # Gọi LLM để lấy kế hoạch ban đầu
#         rsp = _chat(
#             query=DeepPentestPrompt.write_plan, 
#             conversation_id=self.plan_chat_id, 
#             kb_name=Configs.kb_config.kb_name, 
#             kb_query=init_description
#         )

#         # Gọi LLM để sửa lại định dạng JSON nếu cần, trực tiếp trong hàm run
#         fixed_response = _chat(
#             query=DeepPentestPrompt.fix_json.format(raw_response=rsp),
#             conversation_id=self.plan_chat_id,
#             kb_name=Configs.kb_config.kb_name,
#             kb_query=rsp
#         )
#         print(f"*********fixed rsp in run: {fixed_response}*********")
#         # Trích xuất các plan từ JSON đã được sửa
#         extracted_plans = extract_plan_data(fixed_response)
#         return json.dumps(extracted_plans)



#     def update(self, task_result, success_task, fail_task, init_description) -> str:
#         # Gọi LLM để cập nhật kế hoạch dựa trên kết quả task
#         rsp = _chat(
#             query=DeepPentestPrompt.update_plan.format(
#                 current_task=task_result.instruction,
#                 init_description=init_description,
#                 current_code=task_result.code,
#                 task_result=task_result.result,
#                 success_task=success_task,
#                 fail_task=fail_task
#             ),
#             conversation_id=self.plan_chat_id,
#             kb_name=Configs.kb_config.kb_name,
#             kb_query=task_result.instruction
#         )

#         if rsp == "":
#             return rsp  
#         # Gọi LLM để sửa định dạng JSON ngay trong hàm update

#         fixed_response = _chat(
#             query=DeepPentestPrompt.fix_json.format(raw_response=rsp),
#             conversation_id=self.plan_chat_id,
#             kb_name=Configs.kb_config.kb_name,
#             kb_query=rsp
#         )
#         print(f"*********fixed rsp in update: {fixed_response}*********")
#         extracted_plans = extract_plan_data(fixed_response)
#         return json.dumps(extracted_plans)




class WritePlan(BaseModel):
    plan_chat_id: str

    def run(self, init_description) -> str:
        rsp = _chat(query=DeepPentestPrompt.write_plan, conversation_id=self.plan_chat_id, kb_name=Configs.kb_config.kb_name, kb_query=init_description)

        pattern = r"(?:<json>(.*?)</json>|'''json\s*(.*?)\s*'''|```json\s*(.*?)\s*```)"
        match = re.search(pattern, rsp, re.DOTALL)
        # match = re.search(r'<json>(.*?)</json>', rsp, re.DOTALL)
        if match:
            code = match.group(1)
            return code

    def update(self, task_result, success_task, fail_task, init_description) -> str:
        rsp = _chat(
            query=DeepPentestPrompt.update_plan.format(current_task=task_result.instruction,
                                                      init_description=init_description,
                                                      current_code=task_result.code,
                                                      task_result=task_result.result,
                                                      success_task=success_task,
                                                      fail_task=fail_task),
            conversation_id=self.plan_chat_id,
            kb_name=Configs.kb_config.kb_name,
            kb_query=task_result.instruction
        )
        if rsp == "":
            return rsp

        #pattern = r"(?:<json>(.*?)</json>|'''json\s*(.*?)\s*''')"
        #pattern = r"(?:<json>(.*?)</json>|'''json\s*(.*?)\s*'''|```json\s*(.*?)\s*```)"
        # pattern = r"(?:<json>\s*([\s\S]*?)\s*</json>|```json\s*([\s\S]*?)\s*```)"
        # match = re.search(pattern, rsp, re.DOTALL)
        pattern = r"(?:<json>(.*?)</json>|'''json\s*(.*?)\s*'''|```json\s*(.*?)\s*```)"
        match = re.search(pattern, rsp, re.DOTALL)
        # match = re.search(r'<json>(.*?)</json>', rsp, re.DOTALL)
        if match:
            code = match.group(1)
            return code


def parse_tasks(response: str, current_plan: Plan):
    #print(f"#######response: {response}#######")
    response = json.loads(response)

    tasks = import_tasks_from_json(current_plan.id, response)

    current_plan.tasks = tasks

    return current_plan

def preprocess_json_string(json_str):
     # Use a regular expression to find invalid escape sequences
    json_str = re.sub(r'\\([@!])', r'\\\\\1', json_str)

    return json_str

def merge_tasks(response: str, current_plan: Plan):

    # Preprocess the input JSON string
    processed_response = preprocess_json_string(response)

    response = json.loads(processed_response)

    tasks = merge_tasks_from_json(current_plan.id, response, current_plan.tasks)

    current_plan.tasks = tasks

    return current_plan


def import_tasks_from_json(plan_id: str, tasks_json: List[Dict]) -> List[TaskModel]:
    tasks = []
    for idx, task_data in enumerate(tasks_json):
        task = Task(
            plan_id=plan_id,
            sequence=idx,
            action=task_data['action'],
            instruction=task_data['instruction'],
            dependencies=[i for i, t in enumerate(tasks_json)
                          if t['id'] in task_data['dependent_task_ids']]
        )

        tasks.append(task)
    return tasks


def merge_tasks_from_json(plan_id: str, new_tasks_json: List[Dict], old_tasks: List[Task]) -> List[Task]:
    # 获取所有已完成且成功的任务
    completed_tasks_map = {
        task.instruction: task
        for task in old_tasks
        if task.is_finished and task.is_success
    }

    merged_tasks = []

    for instruction, completed_task in completed_tasks_map.items():
        found = False
        for task_data in new_tasks_json:
            if task_data['instruction'] == instruction:
                found = True
                break
        if not found:
            completed_task.sequence = len(merged_tasks)
            completed_task.dependencies = []
            merged_tasks.append(completed_task)

    new_task_id_to_idx = {
        task_data.get('id'): idx+len(merged_tasks)
        for idx, task_data in enumerate(new_tasks_json)
    }
    for idx, task_data in enumerate(new_tasks_json):
        instruction = task_data['instruction']
        sequence = len(merged_tasks)

        if instruction in completed_tasks_map:
            existing_task = completed_tasks_map[instruction]
            existing_task.sequence = sequence
            existing_task.dependencies = [
                new_task_id_to_idx[dep_id]
                for dep_id in task_data['dependent_task_ids']
                if dep_id in new_task_id_to_idx
            ]
            merged_tasks.append(existing_task)
        else:
            new_task = Task(
                plan_id=plan_id,
                sequence=sequence,
                action=task_data['action'],
                instruction=task_data['instruction'],
                dependencies=[
                    new_task_id_to_idx[dep_id]
                    for dep_id in task_data['dependent_task_ids']
                    if dep_id in new_task_id_to_idx
                ],
            )
            merged_tasks.append(new_task)

    return merged_tasks