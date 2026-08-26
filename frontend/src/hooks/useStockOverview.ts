export const stockKeys = {
  all: ['stocks'] as const,
  overview: (code: string) => [...stockKeys.all, 'overview', code] as const,
}
