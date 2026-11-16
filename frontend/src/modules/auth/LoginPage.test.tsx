import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import i18n from '@/app/providers/i18n';
import { AuthLayout } from '@/app/layouts/AuthLayout';
import LoginPage from '@/modules/auth/LoginPage';
import { useAuthStore } from '@/shared/store/authStore';
import { apiError, mockFetch, sampleProfile } from '@/test/fetchMock';

afterEach(() => vi.unstubAllGlobals());

// Declarative router: the data router builds undici Requests that reject jsdom's AbortSignal.
function renderLogin() {
  useAuthStore.setState({ status: 'anonymous' });
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>
        <Route path="/" element={<h1>dashboard-home</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('LoginPage', () => {
  it('validates fields on the client before calling the API', async () => {
    const { fn } = mockFetch({});
    renderLogin();

    await userEvent.click(screen.getByRole('button', { name: 'Войти' }));

    expect(await screen.findAllByText('Обязательное поле.')).toHaveLength(2);
    expect(fn).not.toHaveBeenCalled();
  });

  it('signs in, stores the session in memory and redirects', async () => {
    const { calls } = mockFetch({
      'POST /auth/login/': () => ({ status: 200, body: { access: 'tok', profile: sampleProfile } }),
    });
    renderLogin();

    await userEvent.type(screen.getByLabelText('Email'), 'aibek@example.com');
    await userEvent.type(screen.getByLabelText('Пароль'), 'Str0ng-Passw0rd!');
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }));

    expect(await screen.findByRole('heading', { name: 'dashboard-home' })).toBeInTheDocument();
    expect(calls[0]!.body).toEqual({ email: 'aibek@example.com', password: 'Str0ng-Passw0rd!' });
    expect(useAuthStore.getState().accessToken).toBe('tok');
  });

  it('shows a translated server error', async () => {
    mockFetch({ 'POST /auth/login/': () => apiError(401, 'INVALID_CREDENTIALS') });
    renderLogin();

    await userEvent.type(screen.getByLabelText('Email'), 'aibek@example.com');
    await userEvent.type(screen.getByLabelText('Пароль'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Неверный email или пароль.');
  });

  it('switches interface language without reload', async () => {
    mockFetch({});
    renderLogin();

    await userEvent.selectOptions(screen.getByLabelText('Язык интерфейса'), 'ky');

    expect(await screen.findByRole('button', { name: 'Кирүү' })).toBeInTheDocument();
    expect(i18n.language).toBe('ky');
    expect(document.documentElement.lang).toBe('ky');
  });
});
