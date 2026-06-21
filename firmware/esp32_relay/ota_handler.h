/*
 * ElBot Home Asisten - OTA Handler for ESP32
 *
 * Handles firmware updates via MQTT chunks
 *
 * Protocol:
 * - Backend sends firmware chunks via MQTT topic: elbot/{device_id}/ota
 * - Each chunk is JSON with: { chunk_index, total_chunks, data (base64 encoded) }
 * - After final chunk received, ESP32 verifies and applies update
 */

#ifndef OTA_HANDLER_H
#define OTA_HANDLER_H

#include <ArduinoJson.h>
#include <Update.h>

// OTA buffer size (must be large enough for a single chunk)
#define OTA_CHUNK_SIZE 8192

// Track OTA state
bool otaActive = false;
unsigned int otaExpectedChunks = 0;
unsigned int otaReceivedChunks = 0;
unsigned long otaStartTime = 0;
const unsigned long OTA_TIMEOUT = 300000;  // 5 minutes timeout

// Buffer for base64 decoding
char* decodeBuffer = NULL;

/**
 * Initialize OTA handler
 */
void initOTA() {
  decodeBuffer = (char*)malloc(OTA_CHUNK_SIZE);
  if (!decodeBuffer) {
    Serial.println("ERROR: Could not allocate OTA decode buffer");
  } else {
    Serial.println("OTA handler initialized");
  }
}

/**
 * Base64 decode from ArduinoJson string to binary buffer
 * Returns: number of bytes decoded, or -1 on error
 */
int base64Decode(const char* input, unsigned char* output) {
  // Simple lookup table for base64 characters
  const char b64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

  unsigned int inputLen = strlen(input);
  unsigned int outputLen = 0;
  unsigned int bits = 0;
  unsigned int chars = 0;

  for (unsigned int i = 0; i < inputLen; i++) {
    char c = input[i];
    if (c == '=' || c == '\n' || c == '\r') continue;

    // Find character in base64 table
    int idx = 0;
    while (idx < 64 && b64[idx] != c) idx++;
    if (idx == 64) continue;  // Invalid character

    bits = (bits << 6) | idx;
    chars = (chars + 1) % 4;

    if (chars) {
      output[outputLen++] = (bits >> 16 - 8 * chars) & 0xFF;
    }
  }

  return outputLen;
}

/**
 * Handle OTA data chunk received via MQTT
 */
void handleOTAChunk(StaticJsonDocument<512>& doc) {
  int chunkIndex = doc["chunk"] | -1;
  int totalChunks = doc["total"] | -1;
  const char* data = doc["data"];
  const char* firmwareHash = doc["hash"];

  if (chunkIndex < 0 || totalChunks <= 0 || !data) {
    Serial.println("OTA: Invalid chunk metadata");
    return;
  }

  // Start new OTA update on first chunk
  if (chunkIndex == 0) {
    Serial.printf("OTA: Starting update (%d chunks expected)\n", totalChunks);

    if (otaActive || !Update.begin(UPDATE_SIZE_UNKNOWN)) {
      Serial.printf("OTA: Update.begin() failed: %s\n", Update.errorString());
      return;
    } else {
      otaActive = true;
      otaExpectedChunks = totalChunks;
      otaReceivedChunks = 0;
      otaStartTime = millis();
    }
  }

  // Validate chunk order
  if (!otaActive) {
    Serial.println("OTA: No active update, ignoring chunk");
    return;
  }

  if (chunkIndex != otaReceivedChunks) {
    Serial.printf("OTA: Chunk order error: expected %d, got %d\n", otaReceivedChunks, chunkIndex);
    if (chunkIndex > otaReceivedChunks) {
      Serial.println("OTA: Chunks missed, aborting update");
      Update.abort();
      otaActive = false;
      return;
    }
  }

  // Decode base64 data and write to flash
  int dataLen = base64Decode(data, (unsigned char*)decodeBuffer);

  if (dataLen <= 0) {
    Serial.println("OTA: Base64 decode failed");
    Update.abort();
    otaActive = false;
    return;
  }

  size_t written = Update.write((uint8_t*)decodeBuffer, dataLen);

  if (written != dataLen) {
    Serial.printf("OTA: Write error: %s\n", Update.errorString());
    Update.abort();
    otaActive = false;
    return;
  }

  otaReceivedChunks++;
  Serial.printf("OTA: Chunk %d/%d written (%d bytes)\n", chunkIndex, totalChunks - 1, dataLen);

  // Check if all chunks received
  if (otaReceivedChunks >= otaExpectedChunks) {
    // Verify firmware if hash provided
    bool verified = true;

    if (firmwareHash) {
      unsigned long calculatedHash = calculateFirmwareHash();
      String hashStr = String(calculatedHash, 16);
      verifed = (hashStr == String(firmwareHash));
    }

    if (!verified) {
      Serial.println("OTA: Firmware verification failed!");
      Update.abort();
      otaActive = false;
      return;
    }

    // Complete update
    if (Update.end(true)) {
      Serial.println("OTA: Update successful, restarting...");
      delay(1000);
      ESP.restart();
    } else {
      Serial.printf("OTA: Update.end() failed: %s\n", Update.errorString());
      Update.abort();
      otaActive = false;
    }
  }

  // Timeout check
  if (otaActive && (millis() - otaStartTime > OTA_TIMEOUT)) {
    Serial.println("OTA: Update timeout, aborting");
    Update.abort();
    otaActive = false;
  }
}

/**
 * Simple firmware hash calculation
 */
unsigned long calculateFirmwareHash() {
  // Simple hash for verification (replace with real hash in production)
  unsigned long hash = 5381;
  // Can't easily read back flash in Arduino, so this is a placeholder
  return hash;
}

#endif // OTA_HANDLER_H