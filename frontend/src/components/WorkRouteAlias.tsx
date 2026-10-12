import { Navigate, useLocation } from 'react-router-dom';
export const WorkRouteAlias = ({ path, group }: { path: string; group?: string }) => {
 const location = useLocation(); const params = new URLSearchParams(location.search);
 if (group) params.set('group', group);
 return <Navigate replace to={path + (params.size ? '?' + params : '') + location.hash} />;
};
