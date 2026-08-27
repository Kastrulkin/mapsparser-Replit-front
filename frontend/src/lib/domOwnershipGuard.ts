type DomOwnershipOperation = 'removeChild' | 'insertBefore' | 'replaceChild';

type GuardState = {
  roots: Set<Node>;
  installed: boolean;
  originalRemoveChild: typeof Node.prototype.removeChild;
  originalInsertBefore: typeof Node.prototype.insertBefore;
  originalReplaceChild: typeof Node.prototype.replaceChild;
  patchedRemoveChild?: typeof Node.prototype.removeChild;
  patchedInsertBefore?: typeof Node.prototype.insertBefore;
  patchedReplaceChild?: typeof Node.prototype.replaceChild;
};

const STATE_KEY = '__localosDomOwnershipGuardState__';

const guardGlobal = globalThis as typeof globalThis & {
  [STATE_KEY]?: GuardState;
};

const state: GuardState = guardGlobal[STATE_KEY] ?? {
  roots: new Set<Node>(),
  installed: false,
  originalRemoveChild: Node.prototype.removeChild,
  originalInsertBefore: Node.prototype.insertBefore,
  originalReplaceChild: Node.prototype.replaceChild,
};

guardGlobal[STATE_KEY] = state;

const isInsideGuardedRoot = (node: Node | null): boolean => {
  if (!node) return false;
  return Array.from(state.roots).some((root) => root === node || root.contains(node));
};

const directChildContaining = (parent: Node, descendant: Node): Node | null => {
  let current: Node | null = descendant;
  while (current?.parentNode && current.parentNode !== parent) {
    current = current.parentNode;
  }
  return current?.parentNode === parent ? current : null;
};

const reportRecovery = (operation: DomOwnershipOperation) => {
  console.warn(`[LocalOS] Recovered external DOM ownership conflict during ${operation}.`);
  if (typeof window !== 'undefined' && typeof window.CustomEvent === 'function') {
    window.dispatchEvent(new CustomEvent('localos:dom-ownership-recovered', {
      detail: { operation },
    }));
  }
};

const installPrototypePatches = () => {
  if (state.installed) return;

  const patchedRemoveChild = function <T extends Node>(this: Node, child: T): T {
    if (child.parentNode === this) {
      return state.originalRemoveChild.call(this, child) as T;
    }

    if (isInsideGuardedRoot(this)) {
      const actualParent = child.parentNode;
      if (actualParent && isInsideGuardedRoot(actualParent)) {
        state.originalRemoveChild.call(actualParent, child);
        reportRecovery('removeChild');
        return child;
      }
      if (!child.isConnected) {
        reportRecovery('removeChild');
        return child;
      }
    }

    return state.originalRemoveChild.call(this, child) as T;
  } as typeof Node.prototype.removeChild;

  const patchedInsertBefore = function <T extends Node>(
    this: Node,
    newNode: T,
    referenceNode: Node | null,
  ): T {
    if (referenceNode === null || referenceNode.parentNode === this) {
      return state.originalInsertBefore.call(this, newNode, referenceNode) as T;
    }

    if (isInsideGuardedRoot(this)) {
      const translatedAnchor = directChildContaining(this, referenceNode);
      if (translatedAnchor) {
        reportRecovery('insertBefore');
        return state.originalInsertBefore.call(this, newNode, translatedAnchor) as T;
      }
    }

    return state.originalInsertBefore.call(this, newNode, referenceNode) as T;
  } as typeof Node.prototype.insertBefore;

  const patchedReplaceChild = function <T extends Node>(
    this: Node,
    newChild: Node,
    oldChild: T,
  ): T {
    if (oldChild.parentNode === this) {
      return state.originalReplaceChild.call(this, newChild, oldChild) as T;
    }

    if (isInsideGuardedRoot(this)) {
      const translatedAnchor = directChildContaining(this, oldChild);
      if (translatedAnchor) {
        reportRecovery('replaceChild');
        return state.originalReplaceChild.call(this, newChild, translatedAnchor) as T;
      }
    }

    return state.originalReplaceChild.call(this, newChild, oldChild) as T;
  } as typeof Node.prototype.replaceChild;

  state.patchedRemoveChild = patchedRemoveChild;
  state.patchedInsertBefore = patchedInsertBefore;
  state.patchedReplaceChild = patchedReplaceChild;
  Node.prototype.removeChild = patchedRemoveChild;
  Node.prototype.insertBefore = patchedInsertBefore;
  Node.prototype.replaceChild = patchedReplaceChild;
  state.installed = true;
};

const uninstallPrototypePatches = () => {
  if (!state.installed || state.roots.size > 0) return;
  if (Node.prototype.removeChild === state.patchedRemoveChild) {
    Node.prototype.removeChild = state.originalRemoveChild;
  }
  if (Node.prototype.insertBefore === state.patchedInsertBefore) {
    Node.prototype.insertBefore = state.originalInsertBefore;
  }
  if (Node.prototype.replaceChild === state.patchedReplaceChild) {
    Node.prototype.replaceChild = state.originalReplaceChild;
  }
  state.installed = false;
};

export const installDomOwnershipGuard = (root: Node): (() => void) => {
  state.roots.add(root);
  installPrototypePatches();

  return () => {
    state.roots.delete(root);
    uninstallPrototypePatches();
  };
};
