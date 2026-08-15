/**
 * quant.gateway 工具消费者（规格决策 2：DSH 只做外壳，工具经 FastAPI 网关）。
 *
 * - 无宿主 Bash/FS 编辑；只经 HTTP 调用后端 Tool Gateway（X-API-Key 认证）
 * - 凭据经环境变量注入（QUANT_API_KEY），不入库
 * - 只读/策略工具；模拟下单（approval）在后端工作台审批，不在此暴露
 *
 * register() 接收的 parameters 必须是完整 JSON Schema（本文件手工编译，
 * 等价 defineTool 的 parameterSchemaSpecToJsonSchema 输出）。
 */
export const name = 'quant-gateway'
export const inject = ['tools', 'systemPrompt']

const GATEWAY_URL = process.env.QUANT_GATEWAY_URL ?? 'http://127.0.0.1:8808/api/v1'
const API_KEY = process.env.QUANT_API_KEY ?? ''

const auth = API_KEY ? { 'X-API-Key': API_KEY } : {}

async function invokeGateway(path, body) {
  const resp = await fetch(`${GATEWAY_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...auth },
    body: JSON.stringify(body ?? {}),
  })
  const text = await resp.text()
  let data
  try {
    data = text ? JSON.parse(text) : {}
  } catch {
    data = { raw: text }
  }
  if (!resp.ok) {
    throw new Error(`gateway ${resp.status}: ${JSON.stringify(data)}`)
  }
  return data
}

const renderJson = (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }]

/** 完整 JSON Schema：顶层 type:object + properties + required。 */
function objectSchema(props) {
  const properties = {}
  const required = []
  for (const [key, spec] of Object.entries(props)) {
    properties[key] = { type: spec.type, description: spec.description }
    if (spec.required) required.push(key)
  }
  return {
    type: 'object',
    properties,
    ...(required.length > 0 ? { required } : {}),
  }
}

const strProp = (description, required = false) => ({ type: 'string', description, required })
const intProp = (description) => ({ type: 'integer', description, required: false })

const OUTPUT_SCHEMA = { type: 'object', additionalProperties: true }

/** 直调单个网关工具（读/策略权限；approval 由后端拒绝）。 */
async function runTool(tool, params) {
  return await invokeGateway('/tools/invoke', { tool, params })
}

/** 创建一次 Agent run（分析/回测目标），同步等待完成并返回 run 详情。 */
async function createRunAndWait(objective, strategyParams) {
  const created = await invokeGateway('/agent-runs', {
    objective,
    execute_inline: true,
    ...(strategyParams ? { strategy_params: strategyParams } : {}),
  })
  return await invokeGateway(`/agent-runs/${created.run_id}`, {})
}

const tools = [
  {
    name: 'quant_kline',
    description:
      '查询 A 股日 K 线（只读，经后端类型化工具网关 market.kline，带证据 source_id/as_of/vendor）',
    parameters: objectSchema({
      stock_code: strProp('股票代码，如 sh.600000', true),
      start_date: strProp('开始日期 yyyy-mm-dd'),
      end_date: strProp('结束日期 yyyy-mm-dd'),
    }),
    output: { schema: OUTPUT_SCHEMA, render: renderJson },
    async execute(args) {
      return await runTool('market.kline', args)
    },
  },
  {
    name: 'quant_financials',
    description: '查询股票财报摘要（只读，fundamental.financials，最近 N 个报告期）',
    parameters: objectSchema({
      stock_code: strProp('股票代码，如 sh.600000', true),
      periods: intProp('报告期数量'),
    }),
    output: { schema: OUTPUT_SCHEMA, render: renderJson },
    async execute(args) {
      return await runTool('fundamental.financials', args)
    },
  },
  {
    name: 'quant_run_analysis',
    description:
      '发起一次 Agent 分析/回测 run（自然语言目标；Supervisor 计划 → 专家执行 → 确定性回测审计），返回 run 详情与各节点结构化输出',
    parameters: objectSchema({
      objective: strProp('自然语言研究/回测目标，如「生成 ma_cross 策略并回测验证 sh.600000」', true),
    }),
    output: { schema: OUTPUT_SCHEMA, render: renderJson },
    async execute(args) {
      return await createRunAndWait(args.objective)
    },
  },
]

export const apply = (ctx) => {
  for (const tool of tools) {
    ctx.tools.register(tool)
  }
}
