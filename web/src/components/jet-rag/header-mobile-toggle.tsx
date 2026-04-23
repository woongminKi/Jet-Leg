'use client';

import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function HeaderMobileToggle() {
  const [open, setOpen] = useState(false);

  return (
    <Button
      variant="ghost"
      size="icon"
      className="md:hidden"
      aria-label="메뉴"
      aria-expanded={open}
      onClick={() => setOpen((prev) => !prev)}
    >
      {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
    </Button>
  );
}
