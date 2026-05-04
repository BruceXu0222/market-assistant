"""
LLM 客户端
==========

功能：
1. 调用 OpenAI API（支持 GPT 系列模型）
2. 支持从配置文件加载设置
3. 支持流式/非流式输出
4. 重试机制
5. 日志记录

配置：
- 从 settings.yaml 读取 API 配置
- 支持 OpenAI API 和兼容接口（如 vLLM）
"""

from typing import Optional, List, Dict, Any
from openai import OpenAI
import os
import yaml
from pathlib import Path

# ============================================================================
# 配置加载
# ============================================================================

def load_settings() -> Dict[str, Any]:
    """
    加载 settings.yaml 配置文件

    Returns:
        settings: 配置字典
    """
    # 查找配置文件路径
    config_paths = [
        Path(__file__).parent / "configs" / "settings.yaml",
        Path(__file__).parent.parent / "core" / "configs" / "settings.yaml",
        Path("core/configs/settings.yaml"),
    ]

    for config_path in config_paths:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)

    # 如果找不到配置文件，返回空字典
    print("[警告] 未找到 settings.yaml 配置文件，使用默认配置")
    return {}


# ============================================================================
# LLM 客户端
# ============================================================================

class LLMClient:
    """
    LLM 客户端（支持 OpenAI API 和兼容接口）

    使用方式：
        client = LLMClient()  # 自动从 settings.yaml 加载配置
        response = client.chat("你好，请介绍一下你自己")

        # 或手动指定参数
        client = LLMClient(
            base_url="https://api.openai.com/v1",
            api_key="sk-xxx",
            model="gpt-5.2"
        )
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        初始化 LLM 客户端

        Args:
            base_url: API 服务地址（默认从配置文件读取）
            api_key: API Key（默认从配置文件读取）
            model: 模型名称（默认从配置文件读取）

        优先级：参数 > 环境变量 > 配置文件 > 默认值
        """
        # 加载配置文件
        settings = load_settings()
        llm_config = settings.get("llm", {})

        # 设置 base_url（OpenAI 默认使用官方 API）
        self.base_url = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or llm_config.get("base_url")
            or "https://api.openai.com/v1"
        )

        # 设置 api_key
        self.api_key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
            or llm_config.get("api_key")
            or "EMPTY"
        )

        # 设置模型
        self.model = (
            model
            or os.getenv("OPENAI_MODEL")
            or llm_config.get("model")
            or "gpt-4"
        )

        # 从配置文件读取默认参数
        self.default_temperature = llm_config.get("default_temperature", 0.2)
        self.default_max_tokens = llm_config.get("default_max_tokens", 1024)
        self.temperatures = llm_config.get("temperatures", {})

        # 创建 OpenAI 客户端
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

        print(f"[LLM客户端] 初始化完成，模型: {self.model}")

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        task_type: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        对话接口（非流式）

        Args:
            prompt: 用户输入
            system_prompt: 系统 Prompt（可选）
            temperature: 温度参数（0-1），如不指定则使用配置文件默认值
            max_tokens: 最大输出 token 数，如不指定则使用配置文件默认值
            task_type: 任务类型（plan_gen/plan_repair/narrate），用于选择对应温度
            **kwargs: 其他参数（top_p, frequency_penalty 等）

        Returns:
            response: LLM 输出文本
        """
        # 确定温度参数
        if temperature is None:
            if task_type and task_type in self.temperatures:
                temperature = self.temperatures[task_type]
            else:
                temperature = self.default_temperature

        # 确定 max_tokens
        if max_tokens is None:
            max_tokens = self.default_max_tokens

        # 构建消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        print(f"[LLM客户端] 调用模型: {self.model}, temperature={temperature}, max_tokens={max_tokens}")

        try:
            # 根据模型选择正确的 token 参数名
            # GPT-5 系列使用 max_completion_tokens，其他模型使用 max_tokens
            if "gpt-5" in self.model.lower() or "o1" in self.model.lower():
                token_param = {"max_completion_tokens": max_tokens}
            else:
                token_param = {"max_tokens": max_tokens}

            # 调用 OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                **token_param,
                **kwargs,
            )

            # 提取输出文本
            output = response.choices[0].message.content

            print(f"[LLM客户端] 响应长度: {len(output)} 字符")

            return output

        except Exception as e:
            print(f"[LLM客户端] 调用失败: {e}")
            raise

    def chat_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        task_type: Optional[str] = None,
        **kwargs,
    ):
        """
        对话接口（流式）

        Args:
            同 chat()

        Yields:
            chunk: 输出文本片段
        """
        # 确定温度参数
        if temperature is None:
            if task_type and task_type in self.temperatures:
                temperature = self.temperatures[task_type]
            else:
                temperature = self.default_temperature

        # 确定 max_tokens
        if max_tokens is None:
            max_tokens = self.default_max_tokens

        # 构建消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # 根据模型选择正确的 token 参数名
            if "gpt-5" in self.model.lower() or "o1" in self.model.lower():
                token_param = {"max_completion_tokens": max_tokens}
            else:
                token_param = {"max_tokens": max_tokens}

            # 调用 OpenAI API（流式）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                **token_param,
                stream=True,
                **kwargs,
            )

            # 逐块返回
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            print(f"[LLM客户端] 流式调用失败: {e}")
            raise

    def test_connection(self) -> bool:
        """
        测试连接

        Returns:
            bool: 连接是否正常
        """
        try:
            response = self.chat("你好", max_tokens=10)
            return bool(response)
        except Exception as e:
            print(f"[LLM客户端] 连接测试失败: {e}")
            return False


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    # 测试连接
    client = LLMClient()

    print("=" * 60)
    print("测试 LLM 客户端")
    print("=" * 60)
    print(f"Base URL: {client.base_url}")
    print(f"Model: {client.model}")
    print(f"Default Temperature: {client.default_temperature}")
    print(f"Default Max Tokens: {client.default_max_tokens}")
    print(f"Task Temperatures: {client.temperatures}")
    print("=" * 60)

    # 测试对话
    print("\n测试对话...")
    try:
        response = client.chat("请用一句话介绍 DuckDB")
        print(f"响应: {response}")
    except Exception as e:
        print(f"测试失败: {e}")
