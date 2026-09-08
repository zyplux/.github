import * as z from 'zod';

const RulesetSummarySchema = z.object({ id: z.number(), name: z.string() });

export const RulesetFileSchema = z.object({ name: z.string() });
export const RulesetPagesSchema = z.array(z.array(RulesetSummarySchema));
