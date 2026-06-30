import { afterEach, describe, expect, it } from 'vitest'
import { errorMessage, tokenStore } from '../lib/api'

describe('tokenStore', () => {
  afterEach(() => localStorage.clear())

  it('round-trips and clears JWT token pairs', () => {
    const tokens = { access_token:'access', refresh_token:'refresh', token_type:'bearer', expires_in:900 }
    tokenStore.set(tokens)
    expect(tokenStore.get()).toEqual(tokens)
    tokenStore.clear()
    expect(tokenStore.get()).toBeNull()
  })

  it('recovers safely from malformed storage', () => {
    localStorage.setItem('sentinelx_tokens', '{broken')
    expect(tokenStore.get()).toBeNull()
  })
})

describe('errorMessage', () => {
  it('uses ordinary Error messages', () => {
    expect(errorMessage(new Error('Network offline'))).toBe('Network offline')
  })

  it('does not expose unknown values', () => {
    expect(errorMessage({ secret:'hidden' })).toBe('Something went wrong.')
  })
})
