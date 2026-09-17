export type NewsPost = {
  id: string;
  title?: string;
  text?: string;
  generated_text?: string;
  source?: string;
  url?: string;
  approved?: boolean | number;
  published_at?: string;
  created_at?: string;
  date?: string;
  scheduled_for?: string;
  state?: string;
};

export type NewsTransaction = {
  id: string;
  transaction_date?: string;
  services?: string[];
  amount?: number;
};
