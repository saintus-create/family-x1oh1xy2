import { Circle } from "lucide-react";
import { type CSSProperties } from "react";

// VS Code Codicon-style stroke: crisp, thin, monochrome at any size.
export const ICON_STROKE_WIDTH = 1.5;

// The single, uniform icon used across the entire docs site.
// Change this ONE constant to retheme every icon at once.
const Glyph = Circle;

type IconProps = {
  size?: number | string;
  color?: string;
  strokeWidth?: number | string;
  absoluteStrokeWidth?: boolean;
  className?: string;
  style?: CSSProperties;
  [key: string]: unknown;
};

// Generic uniform icon — always the same minimal glyph, inherits text color.
export const GlyphIcon = (props: IconProps) => (
  <Glyph absoluteStrokeWidth strokeWidth={ICON_STROKE_WIDTH} {...props} />
);

// Large marker for section / division headings.
export const SectionIcon = (props: IconProps) => (
  <GlyphIcon size={28} {...props} />
);

// Small marker for list items and inline callouts.
export const ListItemIcon = (props: IconProps) => (
  <GlyphIcon size={16} {...props} />
);
