#!/usr/bin/env python3
"""Integration test script for the complete parking reservation system."""

import sys
import time
from datetime import datetime, timedelta

# Test the complete workflow
def run_integration_tests():
    """Run comprehensive integration tests."""
    print("\n" + "="*100)
    print("🧪 PARKING RESERVATION SYSTEM - INTEGRATION TESTS")
    print("="*100 + "\n")

    from src.orchestration.graph import get_orchestrator
    from src.data.reservation_manager import get_reservation_manager
    from src.chatbot.admin_agent import get_admin_agent

    orchestrator = get_orchestrator()
    reservation_manager = get_reservation_manager()
    admin_agent = get_admin_agent()

    test_results = []

    # ========================================================================
    # Test 1: Information Query
    # ========================================================================
    print("\n📋 Test 1: Information Query (RAG)")
    print("-" * 100)

    result = orchestrator.process_message("What are your working hours?")

    if result["success"]:
        print(f"✅ PASS - Response received in {result['elapsed_time']:.2f}s")
        print(f"   Response: {result['response'][:100]}...")
        test_results.append(("Information Query", True, result['elapsed_time']))
    else:
        print(f"❌ FAIL - {result.get('error')}")
        test_results.append(("Information Query", False, 0))

    time.sleep(1)

    # ========================================================================
    # Test 2: Reservation Request and Escalation
    # ========================================================================
    print("\n📋 Test 2: Reservation Request and Escalation")
    print("-" * 100)

    start_time = datetime.now() + timedelta(hours=2)
    end_time = datetime.now() + timedelta(hours=4)

    # Step 1: Start reservation
    result = orchestrator.process_message("I want to make a reservation")
    print(f"Bot: {result['response']}")

    # Step 2: Provide name
    result = orchestrator.process_message("John")
    print(f"Bot: {result['response']}")

    # Step 3: Provide surname
    result = orchestrator.process_message("Doe")
    print(f"Bot: {result['response']}")

    # Step 4: Provide car number
    result = orchestrator.process_message("ABC-123")
    print(f"Bot: {result['response']}")

    # Step 5: Provide dates (simplified)
    # In real system, would parse natural language dates
    reservation_data = {
        "name": "John",
        "surname": "Doe",
        "car_number": "ABC-123",
        "start_time": start_time,
        "end_time": end_time,
        "space_type": "standard",
        "contact_info": "john@example.com",
    }

    # Manual escalation for testing
    from src.chatbot.escalation import get_escalation_manager
    escalation_manager = get_escalation_manager()

    escalate_result = escalation_manager.escalate_reservation(
        user_name="John",
        user_surname="Doe",
        car_number="ABC-123",
        start_time=start_time,
        end_time=end_time,
        space_type="standard",
        contact_info="john@example.com",
    )

    if escalate_result["success"]:
        reservation_id = escalate_result["reservation_id"]
        print(f"\n✅ PASS - Reservation escalated successfully")
        print(f"   Reservation ID: {reservation_id}")
        test_results.append(("Reservation Escalation", True, time.time()))
    else:
        print(f"\n❌ FAIL - {escalate_result.get('error')}")
        test_results.append(("Reservation Escalation", False, 0))

    time.sleep(1)

    # ========================================================================
    # Test 3: Admin Approval and MCP Recording
    # ========================================================================
    print("\n📋 Test 3: Admin Approval and MCP Recording")
    print("-" * 100)

    if escalate_result["success"]:
        reservation_id = escalate_result["reservation_id"]

        # Approve reservation
        approve_result = admin_agent.handle_admin_response(f"APPROVE {reservation_id} Approved for testing")

        if approve_result["success"]:
            print(f"✅ PASS - Reservation approved")
            print(f"   Action: {approve_result['action']}")

            # Check if recorded to MCP
            reservation = reservation_manager.get_reservation(reservation_id)

            if reservation and reservation.status.value == "approved":
                print(f"✅ PASS - Reservation status updated in database")

                # Check MCP server file
                import os
                mcp_file = "./data/approved_reservations.txt"

                if os.path.exists(mcp_file):
                    with open(mcp_file, 'r') as f:
                        content = f.read()
                        if "John Doe" in content and "ABC-123" in content:
                            print(f"✅ PASS - Reservation recorded to MCP file")
                            test_results.append(("Admin Approval & Recording", True, time.time()))
                        else:
                            print(f"⚠️  WARNING - Reservation not found in MCP file")
                            test_results.append(("Admin Approval & Recording", False, 0))
                else:
                    print(f"⚠️  WARNING - MCP file does not exist")
                    test_results.append(("Admin Approval & Recording", False, 0))
            else:
                print(f"❌ FAIL - Reservation not found in database")
                test_results.append(("Admin Approval & Recording", False, 0))
        else:
            print(f"❌ FAIL - {approve_result.get('error')}")
            test_results.append(("Admin Approval & Recording", False, 0))

    time.sleep(1)

    # ========================================================================
    # Test 4: Load Testing
    # ========================================================================
    print("\n📋 Test 4: Load Testing - Multiple Queries")
    print("-" * 100)

    queries = [
        "What are your prices?",
        "Where are you located?",
        "What payment methods do you accept?",
        "Tell me about your parking rules",
        "What's the maximum duration?",
    ]

    load_test_results = []
    start_time = time.time()

    for query in queries:
        result = orchestrator.process_message(query)
        load_test_results.append(result["elapsed_time"])

    total_time = time.time() - start_time
    avg_time = sum(load_test_results) / len(load_test_results)

    print(f"✅ Completed {len(queries)} queries in {total_time:.2f}s")
    print(f"   Average response time: {avg_time:.2f}s")
    print(f"   Min: {min(load_test_results):.2f}s, Max: {max(load_test_results):.2f}s")

    if avg_time < 5.0:  # Threshold: 5 seconds
        print(f"✅ PASS - Average response time acceptable")
        test_results.append(("Load Testing", True, avg_time))
    else:
        print(f"⚠️  WARNING - Average response time high")
        test_results.append(("Load Testing", False, avg_time))

    time.sleep(1)

    # ========================================================================
    # Test 5: Guardrails Testing
    # ========================================================================
    print("\n📋 Test 5: Guardrails and Security")
    print("-" * 100)

    # Test PII filtering
    sensitive_queries = [
        "My SSN is 123-45-6789",
        "My credit card is 4532-1234-5678-9010",
    ]

    guardrail_pass = True
    for query in sensitive_queries:
        result = orchestrator.process_message(query)
        if "123-45-6789" in result["response"] or "4532" in result["response"]:
            print(f"❌ FAIL - PII leaked in response: {query}")
            guardrail_pass = False
        else:
            print(f"✅ PASS - PII filtered: {query}")

    test_results.append(("Guardrails", guardrail_pass, 0))

    # ========================================================================
    # Test Summary
    # ========================================================================
    print("\n" + "="*100)
    print("📊 TEST SUMMARY")
    print("="*100)

    passed = sum(1 for _, success, _ in test_results if success)
    total = len(test_results)

    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")

    print("\nDetailed Results:")
    print("-" * 100)

    for test_name, success, duration in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        duration_str = f"({duration:.2f}s)" if duration > 0 else ""
        print(f"{status} - {test_name:.<50} {duration_str}")

    print("\n" + "="*100)

    return passed == total


if __name__ == "__main__":
    try:
        success = run_integration_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
