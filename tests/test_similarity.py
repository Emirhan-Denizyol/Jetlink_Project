import numpy as np
from src.utils.similarity import l2_normalize, cosine_similarity, top_k_similar

def test_l2_normalize_rows_to_unit():
    x = np.array([[3.0, 4.0], [0.0, 0.0]], dtype=np.float32)
    y = l2_normalize(x)
    # Birinci satır birim uzunlukta olmalı
    assert np.allclose(np.linalg.norm(y[0]), 1.0, atol=1e-6)
    # Sıfır vektörü patlamamalı; norm 0 yerine eps ile korunur -> yine 0 vektörü döner
    assert np.allclose(y[1], np.array([0.0, 0.0], dtype=np.float32))

def test_cosine_similarity_shapes_and_values():
    a = np.array([[1, 0], [0, 1]], dtype=np.float32)
    b = np.array([[1, 0], [0, 1], [1, 1]], dtype=np.float32)
    sims = cosine_similarity(a, b)
    assert sims.shape == (2, 3)
    # birim eksenler
    assert np.isclose(sims[0,0], 1.0, atol=1e-6)
    assert np.isclose(sims[1,1], 1.0, atol=1e-6)
    # (1,1) ile her ikisinin kosinüsü ~ 1/sqrt(2)
    root2inv = 1/np.sqrt(2)
    assert np.isclose(sims[0,2], root2inv, atol=1e-6)
    assert np.isclose(sims[1,2], root2inv, atol=1e-6)

def test_top_k_similar_basic():
    keys = np.eye(4, dtype=np.float32)  # 4 adet birim eksen
    q = np.array([1, 0, 0, 0], dtype=np.float32)
    idx, scores = top_k_similar(q, keys, k=2)
    # İlk en yakın 0. indeks (aynı vektör), skor 1.0
    assert idx[0] == 0 and np.isclose(scores[0], 1.0, atol=1e-6)
    # İkinci en yakınlardan herhangi biri 0 ile ortogonal -> skor 0.0
    assert np.isclose(scores[1], 0.0, atol=1e-6)
    assert len(idx) == len(scores) == 2

def test_top_k_similar_handles_large_k_and_zero_k():
    keys = np.random.randn(10, 8).astype(np.float32)
    q = np.random.randn(8).astype(np.float32)
    idx, scores = top_k_similar(q, keys, k=50)  # k > N
    assert len(idx) == len(scores) == 10
    idx0, scores0 = top_k_similar(q, keys, k=0)
    assert len(idx0) == len(scores0) == 0
