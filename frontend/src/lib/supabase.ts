import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://bvhpvzcvcuswiozhyqlk.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ2aHB2emN2Y3Vzd2lvemh5cWxrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI0OTk4NTksImV4cCI6MjA2ODA3NTg1OX0.WN6Yig4ruyDmSDwX12vlZlzRaCOsekXC_WNdtwpeXqE';

export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY); 