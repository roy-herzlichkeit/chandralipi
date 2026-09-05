/**
 * Theme selection.
 *
 * Three states, not two: light, dark, and *unset*. Unset is the default and
 * follows the operating system, which is what a visitor who has never touched
 * the control almost always wants. Only an explicit choice writes to storage
 * and pins `data-theme` on the root element.
 *
 * The initial value is applied by an inline script in index.html before first
 * paint. Doing it here instead would flash the light theme at a visitor who
 * asked for dark, which is the one bug every theme toggle ships with.
 */

export const STORAGE_KEY = 'chandralipi-theme'

export function systemPrefersDark() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function storedTheme() {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    // Private browsing, or storage disabled. Falling back to the system
    // preference is correct here; there is nothing to recover.
    return null
  }
}

export function resolvedTheme() {
  return storedTheme() ?? (systemPrefersDark() ? 'dark' : 'light')
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // Not fatal: the theme still applies for this page view.
  }
}
