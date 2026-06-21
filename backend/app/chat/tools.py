"""
Tool definitions for AI function calling.
Defines OpenAI-compatible function schemas for device control.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "control_device",
            "description": "Menyalakan, mematikan, atau toggle perangkat smart home",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "ID unik perangkat yang akan dikontrol"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["ON", "OFF", "TOGGLE"],
                        "description": "Aksi yang akan dilakukan: ON (nyalakan), OFF (matikan), atau TOGGLE (balik status)"
                    }
                },
                "required": ["device_id", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_status",
            "description": "Mengecek status perangkat smart home saat ini",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "ID unik perangkat yang akan dicek statusnya"
                    }
                },
                "required": ["device_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": "Menampilkan daftar semua perangkat smart home yang terdaftar di sistem",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]
