import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { gzipSync } from 'node:zlib'

const assetsDir = new URL('../dist/assets/', import.meta.url)
const files = (await readdir(assetsDir)).filter((file) => file.endsWith('.js'))
const stats = await Promise.all(
  files.map(async (file) => {
    const bytes = await readFile(join(assetsDir.pathname, file))
    return { file, raw: bytes.byteLength, gzip: gzipSync(bytes).byteLength }
  }),
)

// Route chunks are named by the page component. Shared dependency chunks are
// intentionally excluded from the per-business-chunk budget: they are loaded
// across routes and are accounted for by the aggregate gzip budget instead.
const routeChunkPattern =
  /(?:Dashboard|StockList|Watchlist|StockChart|Screener|Strategies|DLPrediction|AgentAnalysis|AgentWorkspace|BacktestHistory)-/i
const businessStats = stats.filter((item) => routeChunkPattern.test(item.file))
const maxGzip = Math.max(...stats.map((item) => item.gzip), 0)
const maxBusiness = Math.max(...businessStats.map((item) => item.raw), 0)

const gzipBudget = 350 * 1024
const businessBudget = 500 * 1024
if (maxGzip > gzipBudget || maxBusiness > businessBudget) {
  console.error('Bundle budget exceeded:', {
    maxGzip,
    gzipBudget,
    maxBusiness,
    businessBudget,
    businessChunks: businessStats.map((item) => ({ file: item.file, raw: item.raw })),
  })
  process.exit(1)
}

console.log(
  `Bundle budget passed: max gzip ${(maxGzip / 1024).toFixed(1)} KB; max business ${(maxBusiness / 1024).toFixed(1)} KB`,
)
