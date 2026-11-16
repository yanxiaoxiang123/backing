import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const targetRoot = join(root, 'public', 'fonts')
await rm(targetRoot, { recursive: true, force: true })

async function copyFaces(pkg, name, keep) {
  const source = join(root, 'node_modules', pkg)
  const target = join(targetRoot, name)
  const css = await readFile(join(source, 'index.css'), 'utf8')
  const blocks = css.split(/\n\n/).filter((block) => keep.test(block))
  const files = new Set(
    blocks.flatMap((block) => [...block.matchAll(/url\(\.\/files\/([^)]+)\)/g)].map((m) => m[1])),
  )
  if (!files.size) throw new Error(`No font faces selected for ${pkg}`)
  await mkdir(join(target, 'files'), { recursive: true })
  await writeFile(join(target, 'index.css'), `${blocks.join('\n\n')}\n`)
  await cp(join(source, 'LICENSE'), join(target, 'LICENSE'))
  for (const file of files) {
    await cp(join(source, 'files', file), join(target, 'files', file))
  }
}

// Inter only needs Latin for this Chinese-first interface.
await copyFaces('@fontsource-variable/inter', 'inter', /inter-latin-wght-normal/)
// Noto keeps every CJK subset so stock names and rare characters stay covered.
await copyFaces('@fontsource-variable/noto-sans-sc', 'noto-sans-sc', /@font-face/)

console.log('Synced self-hosted fonts into public/fonts')
