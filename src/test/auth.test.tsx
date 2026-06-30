import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it } from 'vitest'
import { AuthProvider, Protected } from '../auth'

afterEach(() => localStorage.clear())

it('redirects anonymous users away from protected pages', async () => {
  render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Secure login</div>}/>
          <Route path="/dashboard" element={<Protected><div>Secret dashboard</div></Protected>}/>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
  expect(await screen.findByText('Secure login')).toBeInTheDocument()
  expect(screen.queryByText('Secret dashboard')).not.toBeInTheDocument()
})
