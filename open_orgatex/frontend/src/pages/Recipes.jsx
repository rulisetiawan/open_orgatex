import React, { useState } from 'react';
import { Plus, Trash2, Calculator, Save, FlaskConical } from 'lucide-react';

const Recipes = () => {
  const [recipeName, setRecipeName] = useState('REACTIVE TURQUOISE BLUE');
  const [fabricWeight, setFabricWeight] = useState(350);
  const [liquorRatio, setLiquorRatio] = useState(8);

  const [chemicals, setChemicals] = useState([
    { id: 1, name: 'Levelling Agent (Aux)', code: 'AUX-01', amount: 1.0, unit: 'g/l', tank: 1 },
    { id: 2, name: 'Glauber Salt', code: 'CH-SALT', amount: 40.0, unit: 'g/l', tank: 1 },
    { id: 3, name: 'Soda Ash', code: 'CH-SODA', amount: 15.0, unit: 'g/l', tank: 1 },
    { id: 4, name: 'Reactive Turquoise Blue G', code: 'DYE-BL1', amount: 2.5, unit: '%', tank: 2 },
    { id: 5, name: 'Reactive Yellow 3RS', code: 'DYE-YL1', amount: 0.15, unit: '%', tank: 2 },
  ]);

  const totalWater = fabricWeight * liquorRatio;

  const calculateAmount = (item) => {
    if (item.unit === '%') {
      return ((item.amount / 100) * fabricWeight * 1000).toFixed(1) + ' g';
    } else {
      return (item.amount * totalWater).toFixed(1) + ' g';
    }
  };

  const handleAddChemical = () => {
    setChemicals([
      ...chemicals,
      {
        id: Date.now(),
        name: 'Zat Kimia Baru',
        code: 'NEW-CHEM',
        amount: 1.0,
        unit: 'g/l',
        tank: 1,
      },
    ]);
  };

  const handleDeleteChemical = (id) => {
    setChemicals(chemicals.filter((c) => c.id !== id));
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-title-md2 font-bold text-black dark:text-white">
            Formulasi Resep Kimia & Zat Warna
          </h2>
          <p className="text-sm font-medium text-body">
            Kalkulasi otomatis penimbangan dan pembuatan order Lab Automation (.DOS)
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleAddChemical}
            className="flex items-center gap-2 rounded bg-primary py-2 px-4 font-medium text-white hover:bg-opacity-90 transition text-sm"
          >
            <Plus className="h-4 w-4" />
            <span>Tambah Bahan</span>
          </button>
        </div>
      </div>

      {/* Parameter Resep & Ringkasan Volume */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-sm border border-stroke bg-white p-5 shadow-default dark:border-strokedark dark:bg-boxdark">
          <label className="mb-2 block text-sm font-medium text-black dark:text-white">
            Nama Resep Pencelupan
          </label>
          <input
            type="text"
            value={recipeName}
            onChange={(e) => setRecipeName(e.target.value)}
            className="w-full rounded border-[1.5px] border-stroke bg-transparent py-2.5 px-4 font-medium text-black dark:text-white outline-none transition focus:border-primary dark:border-form-strokedark dark:bg-form-input"
          />
        </div>

        <div className="rounded-sm border border-stroke bg-white p-5 shadow-default dark:border-strokedark dark:bg-boxdark">
          <label className="mb-2 block text-sm font-medium text-black dark:text-white">
            Berat Kain Simulasi (kg)
          </label>
          <input
            type="number"
            value={fabricWeight}
            onChange={(e) => setFabricWeight(parseFloat(e.target.value) || 0)}
            className="w-full rounded border-[1.5px] border-stroke bg-transparent py-2.5 px-4 font-medium text-black dark:text-white outline-none transition focus:border-primary dark:border-form-strokedark dark:bg-form-input"
          />
        </div>

        <div className="rounded-sm border border-stroke bg-white p-5 shadow-default dark:border-strokedark dark:bg-boxdark">
          <label className="mb-2 block text-sm font-medium text-black dark:text-white">
            Rasio Celup (1 : X)
          </label>
          <div className="flex items-center justify-between">
            <input
              type="number"
              step="0.5"
              value={liquorRatio}
              onChange={(e) => setLiquorRatio(parseFloat(e.target.value) || 0)}
              className="w-24 rounded border-[1.5px] border-stroke bg-transparent py-2.5 px-4 font-medium text-black dark:text-white outline-none transition focus:border-primary dark:border-form-strokedark dark:bg-form-input"
            />
            <div className="text-right">
              <span className="block text-xs text-body">Total Volume Air:</span>
              <span className="font-bold text-base text-primary font-mono">{totalWater} Liter</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabel Bahan Kimia */}
      <div className="rounded-sm border border-stroke bg-white shadow-default dark:border-strokedark dark:bg-boxdark">
        <div className="py-4 px-6 border-b border-stroke dark:border-strokedark flex justify-between items-center">
          <h4 className="text-base font-semibold text-black dark:text-white">
            Daftar Komposisi Obat Bantu & Pewarna
          </h4>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full table-auto">
            <thead>
              <tr className="bg-gray-2 text-left dark:bg-meta-4">
                <th className="py-3 px-4 font-semibold text-xs text-black dark:text-white uppercase">Kode</th>
                <th className="py-3 px-4 font-semibold text-xs text-black dark:text-white uppercase">Nama Bahan</th>
                <th className="py-3 px-4 font-semibold text-xs text-black dark:text-white uppercase">Jumlah</th>
                <th className="py-3 px-4 font-semibold text-xs text-black dark:text-white uppercase">Satuan</th>
                <th className="py-3 px-4 font-semibold text-xs text-black dark:text-white uppercase">Tangki Dosing</th>
                <th className="py-3 px-4 font-semibold text-xs text-black dark:text-white uppercase">Hasil Hitung (Gram)</th>
                <th className="py-3 px-4 font-semibold text-xs text-black dark:text-white uppercase">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {chemicals.map((item) => (
                <tr key={item.id} className="border-b border-stroke dark:border-strokedark hover:bg-gray/50">
                  <td className="py-3 px-4 font-mono text-xs font-bold text-primary">{item.code}</td>
                  <td className="py-3 px-4 text-sm font-medium text-black dark:text-white">{item.name}</td>
                  <td className="py-3 px-4">
                    <input
                      type="number"
                      step="0.01"
                      value={item.amount}
                      onChange={(e) => {
                        const updated = chemicals.map((c) =>
                          c.id === item.id ? { ...c, amount: parseFloat(e.target.value) || 0 } : c
                        );
                        setChemicals(updated);
                      }}
                      className="w-20 rounded border border-stroke bg-transparent py-1 px-2 text-sm outline-none dark:border-form-strokedark"
                    />
                  </td>
                  <td className="py-3 px-4">
                    <select
                      value={item.unit}
                      onChange={(e) => {
                        const updated = chemicals.map((c) =>
                          c.id === item.id ? { ...c, unit: e.target.value } : c
                        );
                        setChemicals(updated);
                      }}
                      className="rounded border border-stroke bg-transparent py-1 px-2 text-sm outline-none dark:border-form-strokedark"
                    >
                      <option value="g/l">g/l</option>
                      <option value="%">% (owf)</option>
                    </select>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`inline-block rounded py-1 px-2.5 text-xs font-bold ${
                        item.tank === 1
                          ? 'bg-meta-5/10 text-meta-5'
                          : 'bg-meta-6/10 text-meta-6'
                      }`}
                    >
                      Tangki {item.tank} ({item.tank === 1 ? 'Aux' : 'Color'})
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono font-bold text-sm text-success">
                    {calculateAmount(item)}
                  </td>
                  <td className="py-3 px-4">
                    <button
                      onClick={() => handleDeleteChemical(item.id)}
                      className="text-danger hover:opacity-80 transition"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Recipes;
