import { useState, useRef } from 'react';
import { api, uploadsUrl } from '../api/client';
import toast from 'react-hot-toast';

const MAX_IMAGES = 10;
const ACCEPT = 'image/jpeg,image/png,image/webp,image/gif';

export default function WishRequestImageManager({ wishRequest, onUpdate, className = '' }) {
  const [uploading, setUploading] = useState(false);
  const [removing, setRemoving] = useState(null);
  const fileInputRef = useRef(null);
  const images = wishRequest?.images || [];

  const handleAddClick = () => {
    if (images.length >= MAX_IMAGES) {
      toast.error(`Maximum ${MAX_IMAGES} images per wish request`);
      return;
    }
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !wishRequest?.wish_request_id) return;
    if (!file.type.match(/^image\/(jpeg|png|webp|gif)$/)) {
      toast.error('Please select a JPEG, PNG, WebP, or GIF image');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image must be under 5MB');
      return;
    }

    setUploading(true);
    try {
      const img = await api.postImage(`/wishrequests/${wishRequest.wish_request_id}/images`, file);
      onUpdate?.({ ...wishRequest, images: [...images, img] });
      toast.success('Image added');
    } catch (err) {
      toast.error(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleRemove = async (img) => {
    if (!wishRequest?.wish_request_id || removing) return;
    if (!confirm('Remove this image?')) return;

    setRemoving(img.image_id);
    try {
      await api.delete(`/wishrequests/${wishRequest.wish_request_id}/images/${img.image_id}`);
      onUpdate?.({
        ...wishRequest,
        images: images.filter((i) => i.image_id !== img.image_id),
      });
      toast.success('Image removed');
    } catch (err) {
      toast.error(err.message || 'Remove failed');
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-3">
        {images.map((img) => (
          <div key={img.image_id} className="relative group">
            <div className="w-20 h-20 rounded-lg overflow-hidden border-2 border-gray-200 bg-gray-100">
              <img
                src={uploadsUrl(img.image_url)}
                alt=""
                className="w-full h-full object-cover"
                onError={(e) => { e.target.src = 'https://via.placeholder.com/80?text=?'; }}
              />
            </div>
            <button
              type="button"
              onClick={() => handleRemove(img)}
              disabled={removing === img.image_id}
              className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-red-500 text-white text-sm font-bold opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600 disabled:opacity-50"
              title="Remove image"
            >
              ×
            </button>
          </div>
        ))}

        {images.length < MAX_IMAGES && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT}
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              type="button"
              onClick={handleAddClick}
              disabled={uploading}
              className="w-20 h-20 rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors disabled:opacity-50"
              title="Add image"
            >
              {uploading ? <span className="text-xs">Uploading…</span> : <span className="text-2xl">+</span>}
            </button>
          </>
        )}
      </div>
      <p className="text-xs text-gray-500 mt-1">
        {images.length} / {MAX_IMAGES} images • JPEG, PNG, WebP, GIF • max 5MB
      </p>
    </div>
  );
}
