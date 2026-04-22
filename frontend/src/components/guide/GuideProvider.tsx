'use client';

import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { GuideBanner } from './GuideBanner';
import { HelpButton } from './HelpButton';
import { HelpDrawer } from './HelpDrawer';
import { getGuideForPath } from '@/data/guideContent';

export function GuideProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const guide = getGuideForPath(pathname);

  return (
    <>
      {guide && <GuideBanner pathname={pathname} text={guide.banner} />}
      {children}
      {guide && (
        <>
          <HelpButton onClick={() => setDrawerOpen(true)} />
          <HelpDrawer
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            sections={guide.sections}
          />
        </>
      )}
    </>
  );
}
