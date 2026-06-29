"""
Tests for the Blackboard shared memory system.
"""

from src.memory.blackboard import Blackboard


class TestBlackboard:
    """Test the Blackboard inter-agent communication system."""

    def test_publish_and_get_result(self):
        bb = Blackboard()
        bb.publish_result("task_1", {"success": True, "summary": "Done"})
        result = bb.get_result("task_1")
        assert result is not None
        assert result["success"] is True
        assert result["summary"] == "Done"

    def test_get_nonexistent_result(self):
        bb = Blackboard()
        assert bb.get_result("nonexistent") is None

    def test_publish_and_subscribe_channel(self):
        bb = Blackboard()
        bb.publish("agent_1", "findings", {"data": [1, 2, 3]})
        result = bb.subscribe("findings")
        assert result is not None
        assert result["data"] == [1, 2, 3]

    def test_subscribe_nonexistent_channel(self):
        bb = Blackboard()
        assert bb.subscribe("ghost_channel") is None

    def test_get_all_results(self):
        bb = Blackboard()
        bb.publish_result("t1", {"success": True})
        bb.publish_result("t2", {"success": False})
        all_results = bb.get_all_results()
        assert len(all_results) == 2
        assert "t1" in all_results
        assert "t2" in all_results

    def test_clear(self):
        bb = Blackboard()
        bb.publish_result("t1", {"success": True})
        bb.publish("a1", "chan", {"x": 1})
        bb.clear()
        assert bb.get_result("t1") is None
        assert bb.subscribe("chan") is None
