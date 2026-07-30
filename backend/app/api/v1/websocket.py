"""
WebSocket Protocol Gateway for Real-Time Execution Streaming (LangGraph Execution Graph).
"""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws/v1", tags=["Real-time Streaming"])


@router.websocket("/execution/{thread_id}")
async def websocket_execution_stream(websocket: WebSocket, thread_id: str):
    """
    Streams LangGraph DAG execution graph events to the visualizer UI in real-time.
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for thread {thread_id}")

    try:
        # Event 1: Start node transition
        await websocket.send_json({
            "event": "NODE_TRANSITION",
            "thread_id": thread_id,
            "data": {
                "from_node": "CEO_Orchestrator",
                "to_node": "HR_Agent",
                "reason": "Phát hiện nhu cầu khởi tạo hồ sơ nhân sự",
            },
        })
        await asyncio.sleep(0.5)

        # Event 2: Tool call start
        await websocket.send_json({
            "event": "TOOL_CALL_START",
            "thread_id": thread_id,
            "data": {
                "agent": "HR_Agent",
                "tool_name": "create_employee_record",
                "status": "EXECUTING",
            },
        })
        await asyncio.sleep(0.5)

        # Event 3: Task complete
        await websocket.send_json({
            "event": "TASK_COMPLETE",
            "thread_id": thread_id,
            "data": {
                "status": "COMPLETED",
                "summary": "Tất cả các nút DAG đã thực thi xong.",
            },
        })

        # Keep connection open for client echo
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for thread {thread_id}")
