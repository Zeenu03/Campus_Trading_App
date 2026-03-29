"""
B+ Tree Implementation
Campus Trading Application - CS432 Database Project

A self-balancing tree data structure that maintains sorted data and allows
efficient insertion, deletion, search, and range queries in O(log n) time.

Key Properties:
- All data is stored in leaf nodes
- Leaf nodes are connected in a doubly-linked list
- Internal nodes only store keys for navigation
- Tree is always balanced (all leaves at same level)
"""

from typing import Any, Optional, List, Tuple
from .node import Node, LeafNode, InternalNode

try:
    from graphviz import Digraph
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False


class BPlusTree:
    """
    B+ Tree implementation supporting CRUD operations and range queries.

    Attributes:
        order: Maximum number of children per internal node
        root: Root node of the tree
    """

    def __init__(self, order: int = 4):
        """
        Initialize an empty B+ Tree.

        Args:
            order: Maximum children per internal node (default: 4)
                   Must be >= 3 for proper B+ Tree behavior
        """
        if order < 3:
            raise ValueError("Order must be at least 3")

        self.order = order
        self.root: Node = LeafNode(order)
        self._size = 0

    # ==================== SEARCH OPERATIONS ====================

    def search(self, key: Any) -> Optional[Any]:
        """
        Search for a key in the B+ Tree.

        Time Complexity: O(log_m n) where m = order, n = number of keys)
        Args:
            key: The key to search for

        Returns:
            Associated value if found, None otherwise
        """
        leaf = self._find_leaf(key)
        return leaf.get_value(key)

    def _find_leaf(self, key: Any) -> LeafNode:
        """
        Traverse from root to the appropriate leaf node for a key.
        
        Args:
            key: The key to search for

        Returns:
            The leaf node that should contain this key
        """
        node = self.root
        while not node.is_leaf():
            node = node.get_child_for_key(key)
        return node

    def _find_position(self, keys: List[Any], key: Any) -> int:
        """
        Binary search to find insertion position in sorted key list.

        Args:
            keys: Sorted list of keys
            key: Key to find position for

        Returns:
            Index where key should be inserted
        """
        left, right = 0, len(keys)
        while left < right:
            mid = (left + right) // 2
            if keys[mid] < key:
                left = mid + 1
            else:
                right = mid
        return left
        
    # ==================== INSERT OPERATIONS ====================

    def insert(self, key: Any, value: Any) -> None:
        """
        Insert a key-value pair into the B+ Tree.

        If the key already exists, its value is updated.

        Time Complexity: O(log_m n)

        Args:
            key: The key to insert
            value: The associated value
        """
        leaf = self._find_leaf(key)

        # Check for duplicate key - update if exists
        for i, k in enumerate(leaf.keys):
            if k == key:
                leaf.values[i] = value
                return

        # Find insertion position
        pos = self._find_position(leaf.keys, key)

        # Insert key-value pair
        leaf.insert_at(pos, key, value)
        self._size += 1

        # Handle overflow if necessary
        if leaf.is_full():
            self._split_leaf(leaf)

    def _split_leaf(self, leaf: LeafNode) -> None:
        """
        Split a full leaf node.

        Creates a new leaf node with the upper half of keys,
        copies the middle key to the parent, and maintains
        the leaf linked list.

        Args:
            leaf: The leaf node to split
        """
        new_leaf = LeafNode(self.order)
        mid = len(leaf.keys) // 2

        # Move upper half to new leaf
        new_leaf.keys = leaf.keys[mid:]
        new_leaf.values = leaf.values[mid:]
        leaf.keys = leaf.keys[:mid]
        leaf.values = leaf.values[:mid]

        # Update linked list pointers
        new_leaf.next = leaf.next
        new_leaf.prev = leaf
        if leaf.next:
            leaf.next.prev = new_leaf
        leaf.next = new_leaf

        # Promote first key of new leaf to parent
        promote_key = new_leaf.keys[0]
        self._insert_into_parent(leaf, promote_key, new_leaf)

    def _insert_into_parent(self, left_child: Node, key: Any, right_child: Node) -> None:
        """
        Insert a key and right child pointer into the parent node.

        If there's no parent (left_child is root), create a new root.

        Args:
            left_child: Existing child (becomes left of new key)
            key: Key to insert in parent
            right_child: New child (becomes right of new key)
        """
        if left_child.parent is None:
            # Create new root
            new_root = InternalNode(self.order)
            new_root.keys = [key]
            new_root.children = [left_child, right_child]
            left_child.parent = new_root
            right_child.parent = new_root
            self.root = new_root
        else:
            parent = left_child.parent

            # Find position for new key
            pos = self._find_position(parent.keys, key)

            # Insert key and child
            parent.keys.insert(pos, key)
            parent.children.insert(pos + 1, right_child)
            right_child.parent = parent

            # Split parent if necessary
            if parent.is_full():
                self._split_internal(parent)


    def _split_internal(self, node: InternalNode) -> None:
        """
        Split a full internal node.

        Creates a new internal node with the upper half,
        promotes the middle key to the parent (not copied),
        and redistributes children.

        Args:
            node: The internal node to split
        """
        new_node = InternalNode(self.order)
        mid = len(node.keys) // 2

        # The middle key is promoted, not copied
        promote_key = node.keys[mid]

        # Move upper half to new node
        new_node.keys = node.keys[mid + 1:]
        new_node.children = node.children[mid + 1:]

        # Update children's parent pointers
        for child in new_node.children:
            child.parent = new_node

        # Keep lower half in original node
        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]

        self._insert_into_parent(node, promote_key, new_node)

    # ==================== DELETE OPERATIONS ====================

    def delete(self, key: Any) -> bool:
        """
        Delete a key from the B+ Tree.

        Time Complexity: O(log_m n)

        Args:
            key: The key to delete

        Returns:
            True if deletion succeeded, False if key not found
        """
        leaf = self._find_leaf(key)

        # Find key in leaf
        try:
            idx = leaf.keys.index(key)
        except ValueError:
            return False  # Key not found

        # Remove key-value pair
        leaf.remove_at(idx)
        self._size -= 1

        # If this is the root leaf, we're done (can have any number of keys)
        if leaf == self.root:
            return True

        # Handle underflow if necessary
        if leaf.is_underflow():
            self._handle_leaf_underflow(leaf)

        return True

    def _handle_leaf_underflow(self, leaf: LeafNode) -> None:
        """
        Handle underflow in a leaf node.

        Strategy:
        1. Try to borrow from left sibling
        2. Try to borrow from right sibling
        3. Merge with a sibling

        Args:
            leaf: The leaf node with underflow
        """
        parent = leaf.parent
        if parent is None:
            return

        idx = parent.children.index(leaf)
        min_keys = leaf.min_keys()

        # Try borrowing from left sibling
        if idx > 0:
            left_sibling = parent.children[idx - 1]
            if len(left_sibling.keys) > min_keys:
                self._borrow_from_prev(parent, idx)
                return

        # Try borrowing from right sibling
        if idx < len(parent.children) - 1:
            right_sibling = parent.children[idx + 1]
            if len(right_sibling.keys) > min_keys:
                self._borrow_from_next(parent, idx)
                return

        # Merge with sibling
        if idx > 0:
            self._merge(parent, idx - 1)
        else:
            self._merge(parent, idx)

    def _merge(self, parent: InternalNode, index: int) -> None:
        """
        Merge child at index with child at index+1 (leaf nodes).

        Args:
            parent: Parent node
            index: Index of the left child to merge
        """
        left_child = parent.children[index]
        right_child = parent.children[index + 1]

        # Merge keys and values
        left_child.keys.extend(right_child.keys)
        left_child.values.extend(right_child.values)

        # Update linked list
        left_child.next = right_child.next
        if right_child.next:
            right_child.next.prev = left_child

        # Remove separator key and right child from parent
        parent.keys.pop(index)
        parent.children.pop(index + 1)

        # Handle parent underflow
        if parent == self.root:
            if not parent.keys:
                self.root = left_child
                left_child.parent = None
        elif parent.is_underflow():
            self._handle_internal_underflow(parent)
            
    def _handle_internal_underflow(self, node: InternalNode) -> None:
        """Handle underflow in an internal node."""
        if node == self.root:
            # If root is empty but has children, make first child the new root
            if not node.keys and node.children:
                self.root = node.children[0]
                self.root.parent = None
            return

        parent = node.parent
        idx = parent.children.index(node)
        min_keys = node.min_keys()

        # Try borrowing from left sibling
        if idx > 0:
            left_sibling = parent.children[idx - 1]
            if len(left_sibling.keys) > min_keys:
                self._borrow_from_prev_internal(parent, idx)
                return

        # Try borrowing from right sibling
        if idx < len(parent.children) - 1:
            right_sibling = parent.children[idx + 1]
            if len(right_sibling.keys) > min_keys:
                self._borrow_from_next_internal(parent, idx)
                return

        # Merge with sibling
        if idx > 0:
            self._merge_internal(parent, idx - 1)
        else:
            self._merge_internal(parent, idx)

    def _merge_internal(self, parent: InternalNode, index: int) -> None:
        """Merge internal nodes."""
        left_child = parent.children[index]
        right_child = parent.children[index + 1]

        # Pull down separator key from parent
        left_child.keys.append(parent.keys[index])

        # Merge keys and children
        left_child.keys.extend(right_child.keys)
        left_child.children.extend(right_child.children)

        # Update parent pointers for moved children
        for child in right_child.children:
            child.parent = left_child

        # Remove from parent
        parent.keys.pop(index)
        parent.children.pop(index + 1)

        # Handle parent underflow
        if parent == self.root:
            if not parent.keys:
                self.root = left_child
                left_child.parent = None
        elif parent.is_underflow():
            self._handle_internal_underflow(parent)

    def _borrow_from_prev(self, parent: InternalNode, index: int) -> None:
        """
        Borrow a key from the left sibling (leaf nodes).

        Args:
            parent: Parent node
            index: Index of the borrowing child
        """
        child = parent.children[index]
        left_sibling = parent.children[index - 1]

        # Move last key-value from left sibling to beginning of child
        key, value = left_sibling.remove_at(len(left_sibling.keys) - 1)
        child.insert_at(0, key, value)

        # Update parent key
        parent.keys[index - 1] = child.keys[0]

    def _borrow_from_next(self, parent: InternalNode, index: int) -> None:
        """
        Borrow a key from the right sibling (leaf nodes).

        Args:
            parent: Parent node
            index: Index of the borrowing child
        """
        child = parent.children[index]
        right_sibling = parent.children[index + 1]

        # Move first key-value from right sibling to end of child
        key, value = right_sibling.remove_at(0)
        child.insert_at(len(child.keys), key, value)

        # Update parent key
        parent.keys[index] = right_sibling.keys[0]
            
    def _borrow_from_prev_internal(self, parent: InternalNode, index: int) -> None:
        """Borrow from left sibling for internal nodes."""
        child = parent.children[index]
        left_sibling = parent.children[index - 1]

        # Move key from parent down to child
        child.keys.insert(0, parent.keys[index - 1])

        # Move last key from sibling up to parent
        parent.keys[index - 1] = left_sibling.keys.pop()

        # Move last child from sibling
        moved_child = left_sibling.children.pop()
        child.children.insert(0, moved_child)
        moved_child.parent = child

    def _borrow_from_next_internal(self, parent: InternalNode, index: int) -> None:
        """Borrow from right sibling for internal nodes."""
        child = parent.children[index]
        right_sibling = parent.children[index + 1]

        # Move key from parent down to child
        child.keys.append(parent.keys[index])

        # Move first key from sibling up to parent
        parent.keys[index] = right_sibling.keys.pop(0)

        # Move first child from sibling
        moved_child = right_sibling.children.pop(0)
        child.children.append(moved_child)
        moved_child.parent = child

    # ==================== UPDATE OPERATION ====================

    def update(self, key: Any, new_value: Any) -> bool:
        """
        Update the value for an existing key.

        Time Complexity: O(log_m n)

        Args:
            key: The key to update
            new_value: The new value

        Returns:
            True if updated, False if key not found
        """
        leaf = self._find_leaf(key)
        return leaf.set_value(key, new_value)

    # ==================== RANGE QUERY ====================

    def range_query(self, start_key: Any, end_key: Any) -> List[Tuple[Any, Any]]:
        """
        Return all key-value pairs where start_key <= key <= end_key.

        Time Complexity: O(log_m n + k) where k = number of results

        Leverages the leaf linked list for efficient sequential access.

        Args:
            start_key: Lower bound (inclusive)
            end_key: Upper bound (inclusive)

        Returns:
            List of (key, value) tuples in the range
        """
        results = []

        # Find the starting leaf
        leaf = self._find_leaf(start_key)

        # Scan through leaves using next pointers
        while leaf:
            for i, key in enumerate(leaf.keys):
                if key > end_key:
                    return results
                if key >= start_key:
                    results.append((key, leaf.values[i]))
            leaf = leaf.next

        return results

    # ==================== UTILITY METHODS ====================

    def get_all(self) -> List[Tuple[Any, Any]]:
        """
        Return all key-value pairs in sorted order.

        Uses the leaf linked list for efficient traversal.

        Returns:
            List of all (key, value) tuples
        """
        results = []

        # Find leftmost leaf
        node = self.root
        while not node.is_leaf():
            node = node.children[0]

        # Traverse linked list
        while node:
            for i, key in enumerate(node.keys):
                results.append((key, node.values[i]))
            node = node.next

        return results

    def get_height(self) -> int:
        """
        Get the height of the tree.

        Returns:
            Number of levels in the tree
        """
        height = 0
        node = self.root
        while not node.is_leaf():
            height += 1
            node = node.children[0]
        return height + 1

    def get_leftmost_leaf(self) -> LeafNode:
        """Get the leftmost leaf node."""
        node = self.root
        while not node.is_leaf():
            node = node.children[0]
        return node

    def get_rightmost_leaf(self) -> LeafNode:
        """Get the rightmost leaf node."""
        node = self.root
        while not node.is_leaf():
            node = node.children[-1]
        return node

    def __len__(self) -> int:
        """Return the number of key-value pairs in the tree."""
        return self._size

    def __contains__(self, key: Any) -> bool:
        """Check if a key exists in the tree."""
        return self.search(key) is not None

    def __repr__(self) -> str:
        return f"BPlusTree(order={self.order}, size={self._size}, height={self.get_height()})"


    # ==================== VISUALIZATION ====================

    def visualize_tree(self, filename: str = 'bptree') -> Optional['Digraph']:
        """
        Generate a Graphviz visualization of the B+ Tree.

        Args:
            filename: Base filename for output (without extension)

        Returns:
            Graphviz Digraph object if graphviz is available, None otherwise
        """
        if not GRAPHVIZ_AVAILABLE:
            print("Graphviz not available. Install with: pip install graphviz")
            return None

        dot = Digraph(comment='B+ Tree')
        dot.attr(rankdir='TB')  # Top to bottom layout
        dot.attr('node', fontsize='10')

        if self.root:
            self._add_nodes(dot, self.root)
            self._add_edges(dot, self.root)
            self._add_leaf_links(dot)

        return dot

    def _add_nodes(self, dot: 'Digraph', node: Node) -> None:
        """
        Recursively add nodes to the Graphviz diagram.

        Args:
            dot: Graphviz Digraph object
            node: Current node to add
        """
        node_id = str(id(node))

        if node.is_leaf():
            # Leaf node: show keys and values
            if node.keys:
                lines = []
                for k, v in zip(node.keys, node.values):
                    v_str = str(v)[:15] + '...' if len(str(v)) > 15 else str(v)
                    lines.append(f"{k}: {v_str}")
                label = '\n'.join(lines)
            else:
                label = "(empty)"

            dot.node(node_id, label,
                    shape='box', color='darkgreen',
                    style='filled', fillcolor='lightgreen')
        else:
            # Internal node: show separator keys
            label = str(node.keys) if node.keys else "[]"

            dot.node(node_id, label,
                    shape='ellipse', color='darkblue',
                    style='filled', fillcolor='lightblue')

            # Recursively add children
            for child in node.children:
                self._add_nodes(dot, child)

    def _add_edges(self, dot: 'Digraph', node: Node) -> None:
        """
        Add edges from internal nodes to their children.

        Args:
            dot: Graphviz Digraph object
            node: Current node
        """
        if not node.is_leaf():
            node_id = str(id(node))
            for child in node.children:
                child_id = str(id(child))
                dot.edge(node_id, child_id)
                self._add_edges(dot, child)

    def _add_leaf_links(self, dot: 'Digraph') -> None:
        """
        Add dashed lines showing the leaf linked list.

        Args:
            dot: Graphviz Digraph object
        """
        # Find leftmost leaf
        leaf = self.get_leftmost_leaf()

        # Create subgraph for same rank
        with dot.subgraph() as s:
            s.attr(rank='same')
            while leaf:
                s.node(str(id(leaf)))
                leaf = leaf.next

        # Add dashed edges between leaves
        leaf = self.get_leftmost_leaf()
        while leaf and leaf.next:
            dot.edge(str(id(leaf)), str(id(leaf.next)),
                    style='dashed', color='red', constraint='false')
            leaf = leaf.next

    def print_tree(self) -> None:
        """Print a text representation of the tree structure."""
        self._print_node(self.root, 0)

    def _print_node(self, node: Node, level: int) -> None:
        """Recursively print nodes with indentation."""
        indent = "  " * level
        if node.is_leaf():
            pairs = list(zip(node.keys, node.values))
            print(f"{indent}Leaf: {pairs}")
        else:
            print(f"{indent}Internal: {node.keys}")
            for child in node.children:
                self._print_node(child, level + 1)
