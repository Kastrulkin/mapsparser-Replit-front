/** The invitation is a one-time secret, not an authenticated identity. */
export const maxAccountInviteCode = (initData: string, search: string): string => {
  const start = new URLSearchParams(initData).get('start_param')
    || new URLSearchParams(search).get('WebAppStartParam')
    || '';
  const match = /^connect_([A-Za-z0-9_-]{43})$/.exec(start);
  return match?.[1] || '';
};
