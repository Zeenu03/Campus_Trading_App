import { useEffect, useState } from 'react';
import { uploadsUrl } from '../api/client';

/**
 * Listing image from upload path; shows an error state if the file is missing (e.g. DB row but no file on disk).
 * @param {'hero' | 'thumb' | 'tile'} variant - hero: fills aspect box; thumb/tile: fills parent w×h
 */
export default function ListingImage({ path, alt = '', className = '', variant = 'tile' }) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [path]);

  const label = 'Unable to load image';
  const textClass =
    variant === 'thumb'
      ? 'text-[9px] leading-tight px-0.5'
      : variant === 'hero'
        ? 'text-sm px-4 text-center'
        : 'text-xs px-2 text-center';

  if (!path || failed) {
    const wrap =
      variant === 'hero'
        ? 'absolute inset-0 flex items-center justify-center bg-gray-100 text-gray-500'
        : 'flex h-full w-full items-center justify-center bg-gray-100 text-gray-500';
    return (
      <div className={`${wrap} ${className}`} role="img" aria-label={label}>
        <span className={textClass}>{label}</span>
      </div>
    );
  }

  return (
    <img
      src={uploadsUrl(path)}
      alt={alt}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
