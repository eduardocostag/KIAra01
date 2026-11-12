"""
Testes TDD para a KIARA Brain (Orquestrador Agentic)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
from kiara_api.platform.brain.orchestrator import KiaraBrain, TaskIntent

def test_brain_routes_video_intent():
    brain = KiaraBrain()
    command = "Gere um vídeo de um robô dançando no estilo futurista"
    intent = brain.analyze_intent(command)
    
    assert intent.action_type == "video_generation"
    assert "robô dançando" in intent.prompt
    assert intent.target_executor == "wan2_1"

def test_brain_routes_voice_intent():
    brain = KiaraBrain()
    command = "Fale para mim qual o próximo compromisso usando voz grave"
    intent = brain.analyze_intent(command)
    
    assert intent.action_type == "text_to_speech"
    assert intent.target_executor == "voice_studio"

def test_brain_routes_general_automation_to_jarvis():
    brain = KiaraBrain()
    command = "Abra o site da Vercel e verifique o último deploy"
    intent = brain.analyze_intent(command)
    
    assert intent.action_type == "general_automation"
    assert intent.target_executor == "open_jarvis"

def test_brain_dispatches_multimodal_task():
    brain = KiaraBrain()
    command = "Crie um vídeo viral sobre inteligência artificial com voz narrativa"
    plan = brain.create_execution_plan(command)
    
    assert len(plan) == 2
    assert plan[0].target_executor == "voice_studio"
    assert plan[1].target_executor == "money_printer_turbo"
