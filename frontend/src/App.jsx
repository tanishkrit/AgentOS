import { useState, useCallback } from 'react'
import PromptScreen from './components/PromptScreen'
import WorkflowScreen from './components/WorkflowScreen'
import './App.css'

function App() {
  const [screen, setScreen] = useState('prompt') // 'prompt' | 'workflow'
  const [approvalMode, setApprovalMode] = useState('manual') // 'manual' | 'auto'
  const [goal, setGoal] = useState('')
  const [plan, setPlan] = useState(null)
  const [tasks, setTasks] = useState([])
  const [logs, setLogs] = useState([])
  const [approvalRequest, setApprovalRequest] = useState(null)
  const [planApprovalPending, setPlanApprovalPending] = useState(false)
  const [workflowStatus, setWorkflowStatus] = useState('planning') // planning | running | completed | failed
  const [createdFiles, setCreatedFiles] = useState([])
  const [screenFrame, setScreenFrame] = useState(null)
  const [cursorPos, setCursorPos] = useState({ cx: 0, cy: 0, sw: 1, sh: 1 })

  // ── Log helper ──────────────────────────────────────────────
  const addLog = useCallback((level, message) => {
    const time = new Date().toLocaleTimeString('en-GB', { hour12: false })
    setLogs(prev => [...prev, { time, level, message, id: Date.now() + Math.random() }])
  }, [])

  // ── Submit Goal ─────────────────────────────────────────────
  const handleSubmit = useCallback(async (goalText) => {
    setGoal(goalText)
    setScreen('workflow')
    setTasks([])
    setLogs([])
    setPlan(null)
    setWorkflowStatus('planning')
    setPlanApprovalPending(false)

    addLog('system', `Goal received: "${goalText.length > 80 ? goalText.slice(0, 80) + '...' : goalText}"`)
    addLog('system', `Approval mode: ${approvalMode}`)
    addLog('system', 'Sending goal to AI planner for decomposition...')

    try {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.submit_goal(goalText, approvalMode)
      } else {
        addLog('warning', 'Running in demo mode (no Python backend detected)')
        setTimeout(() => simulateDemoPlan(goalText), 2000)
      }
    } catch (err) {
      addLog('error', `Failed to submit goal: ${err.message}`)
    }
  }, [approvalMode, addLog])

  // ── Plan Created (from Python) ──────────────────────────────
  const handlePlanCreated = useCallback((planData) => {
    setPlan(planData)
    const newTasks = planData.tasks.map(t => ({
      ...t,
      status: 'pending',
      result: null,
    }))
    setTasks(newTasks)
    addLog('success', `Plan created: ${planData.summary}`)
    addLog('system', `${newTasks.length} tasks generated.`)

    if (approvalMode === 'manual') {
      setWorkflowStatus('awaiting-approval')
      setPlanApprovalPending(true)
    } else {
      setWorkflowStatus('running')
    }
  }, [approvalMode, addLog])

  // ── Task Status Update (from Python) ────────────────────────
  const handleTaskStatus = useCallback((data) => {
    setTasks(prev => prev.map(t =>
      t.id === data.task_id
        ? { ...t, status: data.status, result: data.result || (data.summary ? { summary: data.summary } : t.result) }
        : t
    ))

    const statusIcons = { pending: '⏳', thinking: '🧠', running: '▶️', completed: '✅', failed: '❌', 'waiting-approval': '⚠️' }
    const icon = statusIcons[data.status] || '•'
    const level = data.status === 'failed' ? 'error' : data.status === 'completed' ? 'success' : 'agent'
    addLog(level, `${icon} ${data.task_id} → ${data.status}${data.summary ? ': ' + data.summary : ''}`)
  }, [addLog])

  // ── Log Message (from Python) ───────────────────────────────
  const handleLogMessage = useCallback((data) => {
    addLog(data.level || 'agent', `[${data.agent_id}] ${data.message}`)
  }, [addLog])

  // ── Approval Request (from Python) ──────────────────────────
  const handleApprovalRequest = useCallback((data) => {
    setApprovalRequest(data)
    // Update the related task to 'waiting-approval'
    setTasks(prev => prev.map(t =>
      data.request_id.includes(t.id)
        ? { ...t, status: 'waiting-approval' }
        : t
    ))
    addLog('warning', `⚠️ Approval required: ${data.description}`)
  }, [addLog])

  // ── Workflow Complete (from Python) ─────────────────────────
  const handleWorkflowComplete = useCallback((data) => {
    const isSuccess = (data.failed || 0) === 0
    setWorkflowStatus(isSuccess ? 'completed' : 'failed')
    addLog('success', `🏁 Workflow finished. ${data.completed}/${data.total} tasks succeeded.`)

    // Track any files created during workflow
    if (data.created_files && data.created_files.length > 0) {
      setCreatedFiles(data.created_files)
      data.created_files.forEach(f => {
        addLog('success', `📂 Created file: ${f}`)
      })
    }
  }, [addLog])

  // ── Workflow Results (from Python) ──────────────────────────
  const handleWorkflowResults = useCallback((data) => {
    if (data.created_files && data.created_files.length > 0) {
      setCreatedFiles(data.created_files)
    }
  }, [])

  // ── Screen Update (from Python) ─────────────────────────────
  const handleScreenUpdate = useCallback((data) => {
    setScreenFrame(data.frame)
    setCursorPos({ cx: data.cx, cy: data.cy, sw: data.sw, sh: data.sh })
  }, [])

  // ── Respond to Approval ─────────────────────────────────────
  const handleRespondApproval = useCallback(async (approved) => {
    if (!approvalRequest) return
    const desc = approvalRequest.description

    addLog(approved ? 'success' : 'warning', `User ${approved ? 'approved' : 'denied'}: ${desc}`)

    setTasks(prev => prev.map(t =>
      approvalRequest.request_id.includes(t.id)
        ? { ...t, status: approved ? 'running' : 'failed' }
        : t
    ))

    if (window.pywebview && window.pywebview.api) {
      await window.pywebview.api.respond_approval(approvalRequest.request_id, approved)
    }
    setApprovalRequest(null)
  }, [approvalRequest, addLog])

  // ── Respond to Plan Approval ────────────────────────────────
  const handlePlanApproval = useCallback(async (approved) => {
    setPlanApprovalPending(false)
    if (approved) {
      addLog('success', '✅ Workflow approved. Starting execution...')
      setWorkflowStatus('running')
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.approve_plan(true)
      } else {
        // Demo mode: simulate execution
        simulateDemoExecution()
      }
    } else {
      addLog('warning', '❌ Workflow rejected by user.')
      setWorkflowStatus('failed')
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.approve_plan(false)
      }
    }
  }, [addLog])

  // ── Demo Simulation ─────────────────────────────────────────
  const simulateDemoPlan = useCallback((goalText) => {
    const demoPlan = {
      summary: `Demo plan for: ${goalText.length > 40 ? goalText.slice(0, 40) + '...' : goalText}`,
      tasks: [
        { id: 'task_1', description: 'Search the web for relevant information', agent_type: 'research', depends_on: [], parameters: { query: goalText } },
        { id: 'task_2', description: 'Open browser and visit top results', agent_type: 'browser', depends_on: ['task_1'], parameters: { url: 'https://example.com' } },
        { id: 'task_3', description: 'Extract and compile data from pages', agent_type: 'research', depends_on: ['task_2'], parameters: {} },
        { id: 'task_4', description: 'Create summary report document', agent_type: 'desktop', depends_on: ['task_3'], parameters: { app: 'notepad' } },
        { id: 'task_5', description: 'Send results via email', agent_type: 'email', depends_on: ['task_4'], parameters: {} },
      ],
    }
    handlePlanCreated(demoPlan)

    if (approvalMode === 'auto') {
      simulateDemoExecutionWithTasks(demoPlan.tasks)
    }
  }, [approvalMode, handlePlanCreated])

  const simulateDemoExecution = useCallback(() => {
    // Use current tasks from plan
    setTasks(prev => {
      simulateDemoExecutionWithTasks(prev)
      return prev
    })
  }, [])

  const simulateDemoExecutionWithTasks = (taskList) => {
    let delay = 500
    taskList.forEach((task, i) => {
      setTimeout(() => handleTaskStatus({ task_id: task.id, status: 'thinking' }), delay)
      delay += 1200
      setTimeout(() => handleTaskStatus({ task_id: task.id, status: 'running' }), delay)
      delay += 2000
      setTimeout(() => handleTaskStatus({ task_id: task.id, status: 'completed', summary: `Done: ${task.description}` }), delay)
      delay += 500
      if (i === taskList.length - 1) {
        setTimeout(() => handleWorkflowComplete({ total: taskList.length, completed: taskList.length, failed: 0 }), delay + 500)
      }
    })
  }

  // ── Register global bridge functions for Python ─────────────
  if (typeof window !== 'undefined') {
    window.onPlanCreated = handlePlanCreated
    window.onTaskStatus = handleTaskStatus
    window.onLogMessage = handleLogMessage
    window.onApprovalRequest = handleApprovalRequest
    window.onWorkflowComplete = handleWorkflowComplete
    window.onWorkflowResults = handleWorkflowResults
    window.onScreenUpdate = handleScreenUpdate
  }

  return (
    <>
      {screen === 'prompt' && (
        <PromptScreen
          approvalMode={approvalMode}
          onApprovalModeChange={setApprovalMode}
          onSubmit={handleSubmit}
        />
      )}
      {screen === 'workflow' && (
        <WorkflowScreen
          goal={goal}
          tasks={tasks}
          logs={logs}
          workflowStatus={workflowStatus}
          planApprovalPending={planApprovalPending}
          approvalRequest={approvalRequest}
          createdFiles={createdFiles}
          screenFrame={screenFrame}
          cursorPos={cursorPos}
          onBack={() => setScreen('prompt')}
          onRespondApproval={handleRespondApproval}
          onPlanApproval={handlePlanApproval}
        />
      )}
    </>
  )
}

export default App
