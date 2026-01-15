
import os
import processor

print("Testing Prompt Loading...")

# Test Lighting Prompts
print(f"Lighting Prompts in memory: {len(processor.LIGHTING_PROMPTS)}")
assert len(processor.LIGHTING_PROMPTS) > 0, "Lighting prompts should not be empty"
print(f"First prompt: {processor.LIGHTING_PROMPTS[0]}")

# Test System Prompt
print(f"System Prompt: {processor.SYSTEM_PROMPT}")
assert "Architectural" in processor.SYSTEM_PROMPT or "architectural" in processor.SYSTEM_PROMPT or len(processor.SYSTEM_PROMPT) > 0

print("Verification Successful!")
