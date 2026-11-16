import { z } from 'zod';

import { LANGUAGES } from '@/shared/api/types';

/** Messages are i18n keys in the `auth` namespace; the server stays the final validator. */
export const PASSWORD_MIN = 10;

export const loginSchema = z.object({
  email: z.string().trim().min(1, 'validation.required').email('validation.emailInvalid'),
  password: z.string().min(1, 'validation.required'),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  display_name: z.string().trim().min(1, 'validation.required').max(80),
  email: z.string().trim().min(1, 'validation.required').email('validation.emailInvalid'),
  password: z.string().min(PASSWORD_MIN, 'validation.passwordMin').max(128),
  timezone: z.string().min(1, 'validation.required'),
  language: z.enum(LANGUAGES),
});
export type RegisterValues = z.infer<typeof registerSchema>;
