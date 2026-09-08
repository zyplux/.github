import * as z from 'zod';

export const RulesetFileSchema = z.object({ name: z.string() });
export const RulesetPagesSchema = z.array(z.array(z.object({ id: z.number(), name: z.string() })));
