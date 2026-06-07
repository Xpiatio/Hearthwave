/// <reference types="vitest/globals" />

declare module 'jest-axe' {
  import type { AxeResults, RunOptions, Spec, ImpactValue } from 'axe-core'

  export interface JestAxeConfigureOptions extends RunOptions {
    globalOptions?: Spec | undefined
    impactLevels?: ImpactValue[]
  }

  export type JestAxe = (
    html: Element | string,
    options?: RunOptions
  ) => Promise<AxeResults>

  export const axe: JestAxe

  export function configureAxe(options?: JestAxeConfigureOptions): JestAxe

  export const toHaveNoViolations: {
    toHaveNoViolations: (results?: Partial<AxeResults>) => {
      actual: unknown[]
      message(): string
      pass: boolean
    }
  }
}

declare module '@vitest/expect' {
  interface Assertion<R = any> {
    toHaveNoViolations(): R
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void
  }
}
