import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, errorMessage, services, tokenStore } from '../lib/api'

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
    localStorage.setItem('shieldiq_tokens', '{broken')
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

describe('digital arrest API contract', () => {
  afterEach(() => vi.restoreAllMocks())

  it('sends analysis only to the persistent digital-arrest endpoint', async () => {
    const response = { case_id:'case-1', risk_score:94 }
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data:response })
    const payload = {
      caller_number:'+919876543210', transcript:'CBI demands an urgent transfer',
      duration:300, video_call:true, country:'India', spoof_detected:true,
    }
    await expect(services.digitalArrest.analyze(payload)).resolves.toEqual(response)
    expect(post).toHaveBeenCalledWith('/digital-arrest/analyze', payload)
  })

  it('uses authenticated case action and report endpoints', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data:{ status:'ok' } })
    await services.digitalArrest.action('case-1', 'block')
    await services.digitalArrest.report('case-1')
    expect(post).toHaveBeenNthCalledWith(1, '/digital-arrest/case-1/actions', { action:'block' })
    expect(post).toHaveBeenNthCalledWith(2, '/digital-arrest/report', { case_id:'case-1', total_victims:1 })
  })
})

describe('currency forensic API contract', () => {
  afterEach(() => vi.restoreAllMocks())

  it('submits the actual image and location to the persistent analyzer', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data:{ case_id:'currency-1' } })
    const file = new File(['image-bytes'], 'note.png', { type:'image/png' })
    await services.currency.analyze(file, 'Delhi Branch')
    expect(post).toHaveBeenCalledOnce()
    expect(post.mock.calls[0][0]).toBe('/currency/analyze')
    const form = post.mock.calls[0][1] as FormData
    expect(form.get('image')).toBe(file)
    expect(form.get('location')).toBe('Delhi Branch')
  })
})
