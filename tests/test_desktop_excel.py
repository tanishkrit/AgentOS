import pytest
import pyautogui
from unittest.mock import MagicMock, patch
from src.agents.desktop_agent import DesktopAgent
from src.memory.blackboard import Blackboard

def test_excel_recipe_visible_resume_flow():
    """
    Test that when pyautogui.FailSafeException is raised during visible Excel entry,
    the agent prompts the user to CONTINUE/RESUME.
    If the user approves 'resume', it should resume typing.
    If they deny 'resume' but approve 'fallback_bg', it should fall back to background writing.
    """
    blackboard = Blackboard()
    agent = DesktopAgent("desktop_agent", blackboard)

    mock_excel_tool = MagicMock()
    mock_desktop_tool = MagicMock()

    # We will raise FailSafeException once on the first row type, then succeed
    call_count = 0
    def side_effect_type_text(text):
        nonlocal call_count
        if text == "row1_val1" and call_count == 0:
            call_count += 1
            raise pyautogui.FailSafeException()
        pass

    mock_desktop_tool.type_text_unicode = MagicMock(side_effect=side_effect_type_text)

    headers = ["Col1"]
    rows = [["row1_val1"], ["row2_val1"]]

    # Let's mock request_approval
    # 1. Initial Excel approval -> True
    # 2. Halt resume prompt -> True
    agent.request_approval = MagicMock(side_effect=[
        True,  # initial file creation approval
        True,  # resume approval when halted
    ])

    # Let's construct a dependency data payload that will resolve to these headers/rows
    dep_data = {
        "dep_1": {
            "structured_data": [{"col1": "row1_val1"}, {"col1": "row2_val1"}],
            "structured_fields": ["col1"]
        }
    }

    with patch("time.sleep") as mock_sleep:
        # Patch excel_tool and desktop_tool instantiation inside the agent's execute, 
        # or we can pass mock tools or mock methods.
        # Actually, in _excel_recipe, it takes excel_tool and desktop_tool as arguments!
        res = agent._excel_recipe(
            excel_tool=mock_excel_tool,
            desktop_tool=mock_desktop_tool,
            dependency_data=dep_data,
            parameters={}
        )

    # Verify resume was called
    assert agent.request_approval.call_count == 2
    agent.request_approval.assert_any_call(
        "Live Excel entry was interrupted. Would you like to CONTINUE/RESUME live typing from row 1? (Please select the correct cell in Excel first, then click Yes)"
    )
    # Check that type_text_unicode was eventually called with the row data
    mock_desktop_tool.type_text_unicode.assert_any_call("row1_val1")
    mock_desktop_tool.type_text_unicode.assert_any_call("row2_val1")
    assert res["success"] is True
    assert "visibly" in res["summary"]

def test_excel_recipe_visible_fallback_flow():
    """
    Test that when pyautogui.FailSafeException is raised, if the user rejects resume
    but accepts background fallback, the agent executes the background fallback.
    """
    blackboard = Blackboard()
    agent = DesktopAgent("desktop_agent", blackboard)

    mock_excel_tool = MagicMock()
    mock_desktop_tool = MagicMock()

    # Raise FailSafeException
    mock_desktop_tool.type_text_unicode = MagicMock(side_effect=pyautogui.FailSafeException)

    # Let's mock request_approval
    # 1. Initial Excel approval -> True
    # 2. Halt resume prompt -> False
    # 3. Fallback to background prompt -> True
    agent.request_approval = MagicMock(side_effect=[
        True,  # initial file creation approval
        False, # reject resume
        True,  # approve fallback background
    ])
    
    mock_excel_tool.create_workbook.return_value = "dummy.xlsx"

    dep_data = {
        "dep_1": {
            "structured_data": [{"col1": "row1_val1"}],
            "structured_fields": ["col1"]
        }
    }

    with patch("time.sleep") as mock_sleep:
        res = agent._excel_recipe(
            excel_tool=mock_excel_tool,
            desktop_tool=mock_desktop_tool,
            dependency_data=dep_data,
            parameters={}
        )

    # Verify the fallback logic ran
    mock_excel_tool.create_workbook.assert_called_once()
    assert res["success"] is True
    assert "background" in res["summary"]
