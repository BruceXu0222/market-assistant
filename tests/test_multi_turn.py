"""
多轮对话测试脚本
================

测试场景：
1. 成交额最高的5只股票
2. "中兴通讯"看起来今天很活跃，展示一下"中兴通讯"今天从15:00到15:30的行情数据
3. "中兴通讯"今天有主力资金流入迹象吗

使用方法：
1. 确保 API 服务正在运行: python -m app.api
2. 运行测试: python tests/test_multi_turn.py
"""

import requests
import json
from typing import Optional

API_BASE_URL = "http://localhost:8080"


def send_message(message: str, session_id: Optional[str] = None, debug: bool = True) -> dict:
    """发送消息到 API"""
    response = requests.post(
        f"{API_BASE_URL}/chat",
        json={
            "message": message,
            "session_id": session_id,
            "debug": debug,
        },
    )
    response.raise_for_status()
    return response.json()


def print_result(turn: int, message: str, result: dict):
    """打印结果"""
    print(f"\n{'='*60}")
    print(f"第 {turn} 轮对话")
    print(f"{'='*60}")
    print(f"用户: {message}")
    print(f"\n助手解读: {result['commentary']}")

    if result.get("table"):
        print(f"\n结果表格 ({len(result['table'])} 条记录):")
        # 只显示前3条
        for i, row in enumerate(result["table"][:3]):
            print(f"  {i+1}. {row}")
        if len(result["table"]) > 3:
            print(f"  ... (还有 {len(result['table']) - 3} 条)")

    if result.get("field_explanations"):
        print(f"\n字段解释:")
        for field, explanation in result["field_explanations"].items():
            print(f"  - {field}: {explanation}")

    if result.get("debug"):
        print(f"\n调试信息:")
        plan = result["debug"].get("plan", {})
        print(f"  - query_type: {plan.get('query_type')}")
        print(f"  - analysis_type: {plan.get('analysis_type', 'N/A')}")
        print(f"  - intent: {plan.get('intent')}")


def main():
    print("=" * 60)
    print("多轮对话测试")
    print("=" * 60)

    # 测试场景
    test_cases = [
        "成交额最高的5只股票",
        "\"中兴通讯\"看起来今天很活跃，展示一下\"中兴通讯\"今天从15:00到15:30的行情数据",
        "\"中兴通讯\"今天有主力资金流入迹象吗",
    ]

    session_id = None

    for i, message in enumerate(test_cases, 1):
        try:
            result = send_message(message, session_id=session_id)

            # 保存 session_id 以便后续请求
            if not session_id:
                session_id = result["session_id"]

            print_result(i, message, result)

        except requests.exceptions.ConnectionError:
            print(f"\n错误: 无法连接到 API 服务。请确保服务正在运行:")
            print(f"  python -m app.api")
            break
        except Exception as e:
            print(f"\n第 {i} 轮对话失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"错误详情: {e.response.json()}")
                except:
                    print(f"响应内容: {e.response.text}")

    print(f"\n{'='*60}")
    print("测试完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
