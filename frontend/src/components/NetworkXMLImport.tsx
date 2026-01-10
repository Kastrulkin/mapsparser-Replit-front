import { useState } from 'react';
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import newAuth from '@/lib/auth_new';

interface NetworkXMLImportProps {
    networkId: string;
    onImportComplete: () => void;
}

interface ImportResult {
    success: boolean;
    created_count?: number;
    summary?: {
        total: number;
        with_coordinates: number;
        with_phone: number;
        with_email: number;
        duplicates_skipped: number;
    };
    error?: string;
}

export function NetworkXMLImport({ networkId, onImportComplete }: NetworkXMLImportProps) {
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<ImportResult | null>(null);
    const [dragActive, setDragActive] = useState(false);

    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const droppedFile = e.dataTransfer.files[0];
            if (droppedFile.name.endsWith('.xml')) {
                setFile(droppedFile);
                setResult(null);
            } else {
                setResult({ success: false, error: 'Файл должен быть в формате XML' });
            }
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const selectedFile = e.target.files[0];
            if (selectedFile.name.endsWith('.xml')) {
                setFile(selectedFile);
                setResult(null);
            } else {
                setResult({ success: false, error: 'Файл должен быть в формате XML' });
            }
        }
    };

    const handleImport = async () => {
        if (!file) return;

        setLoading(true);
        setResult(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await newAuth.makeRequest(
                `/networks/${networkId}/import-xml`,
                {
                    method: 'POST',
                    body: formData,
                }
            );

            if (response.success) {
                setResult(response as ImportResult);
                setTimeout(() => {
                    onImportComplete();
                }, 2000);
            } else {
                setResult({ success: false, error: response.error || 'Неизвестная ошибка' });
            }
        } catch (error: any) {
            console.error('Import error:', error);
            setResult({
                success: false,
                error: error.message || 'Ошибка при импорте XML'
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Upload className="w-5 h-5" />
                    Импорт точек сети из XML
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Drag & Drop Zone */}
                <div
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    className={`
            border-2 border-dashed rounded-lg p-8 text-center transition-colors
            ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
          `}
                >
                    <input
                        type="file"
                        accept=".xml"
                        onChange={handleFileChange}
                        className="hidden"
                        id="xml-upload"
                        disabled={loading}
                    />
                    <label
                        htmlFor="xml-upload"
                        className="cursor-pointer flex flex-col items-center gap-3"
                    >
                        <div className="p-3 bg-gray-100 rounded-full">
                            <FileText className="w-8 h-8 text-gray-600" />
                        </div>
                        {file ? (
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-gray-900">{file.name}</p>
                                <p className="text-xs text-gray-500">
                                    {(file.size / 1024).toFixed(1)} KB
                                </p>
                            </div>
                        ) : (
                            <>
                                <p className="text-sm font-medium text-gray-700">
                                    Нажмите для выбора или перетащите XML файл
                                </p>
                                <p className="text-xs text-gray-500">
                                    Выгрузка из Яндекс.Бизнес (Автоматизация → Выгрузить данные)
                                </p>
                            </>
                        )}
                    </label>
                </div>

                {/* Import Button */}
                {file && !result?.success && (
                    <Button
                        onClick={handleImport}
                        disabled={loading}
                        className="w-full"
                        size="lg"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Импортируем...
                            </>
                        ) : (
                            <>
                                <Upload className="mr-2 h-4 w-4" />
                                Импортировать точки
                            </>
                        )}
                    </Button>
                )}

                {/* Success Message */}
                {result && result.success && result.summary && (
                    <Alert className="bg-green-50 border-green-200">
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                        <AlertDescription className="text-green-800">
                            <div className="space-y-2">
                                <p className="font-semibold">
                                    Успешно импортировано {result.created_count} точек!
                                </p>
                                <div className="text-sm space-y-1">
                                    <p>• С координатами: {result.summary.with_coordinates}</p>
                                    <p>• С телефонами: {result.summary.with_phone}</p>
                                    <p>• С email: {result.summary.with_email}</p>
                                    {result.summary.duplicates_skipped > 0 && (
                                        <p className="text-amber-700">
                                            • Пропущено дубликатов: {result.summary.duplicates_skipped}
                                        </p>
                                    )}
                                </div>
                            </div>
                        </AlertDescription>
                    </Alert>
                )}

                {/* Error Message */}
                {result && !result.success && (
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                            {result.error || 'Произошла ошибка при импорте'}
                        </AlertDescription>
                    </Alert>
                )}
            </CardContent>
        </Card>
    );
}
