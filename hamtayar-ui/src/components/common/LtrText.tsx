import type { ReactNode } from 'react';

type LtrTextProps = {
  children: ReactNode;
  className?: string;
  as?: 'span' | 'div' | 'pre';
};

export function LtrText({ children, className, as: Component = 'span' }: LtrTextProps) {
  return (
    <Component dir="ltr" className={className}>
      {children}
    </Component>
  );
}
