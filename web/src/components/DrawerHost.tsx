import { ContaDetailDrawer } from './ContaDetailDrawer';
import { RuleDetailDrawer } from './RuleDetailDrawer';
import { useDrawer } from '../store/drawer';

export function DrawerHost() {
  const { state } = useDrawer();
  if (!state) return null;
  if (state.kind === 'rule') return <RuleDetailDrawer ruleId={state.payload} />;
  return <ContaDetailDrawer contaContabil={state.payload} />;
}
