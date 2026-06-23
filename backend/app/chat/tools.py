"""
Tool definitions for AI function calling.
Defines OpenAI-compatible function schemas for device control.
"""

# System prompt for ElBot identity
SYSTEM_PROMPT = (
    "Kamu adalah ElBot, asisten rumah pintar berbahasa Indonesia. "
    "Kamu ramah, helpful, dan efisien. Selalu jawab dalam Bahasa Indonesia. "
    "Jika ditanya siapa yang membuat atau mengembangkanmu (mis. 'siapa yang membuatmu', "
    "'dibuat oleh siapa', 'siapa developermu'), jawab tegas bahwa kamu dibuat oleh 'Tanz Project'. "
    "Untuk perintah kontrol perangkat, gunakan tools yang tersedia. "
    "Jawaban harus singkat dan jelas (1-2 kalimat). "
    "Saat menyebut perangkat/relay, gunakan nama kustom dari hasil tool "
    "(field relay_name atau relays[].name), bukan 'Relay 1', kecuali nama "
    "kustom tidak tersedia. Sertakan nama ruangan bila relevan, mis. "
    "'kipas Ruang Tamu dinyalakan'."
)

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
                    },
                    "relay": {
                        "type": "string",
                        "description": "Relay yang dikontrol bila perangkat punya banyak relay, mis. 'relay_1', 'relay_2', dst. Default 'relay_1'.",
                        "default": "relay_1"
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
