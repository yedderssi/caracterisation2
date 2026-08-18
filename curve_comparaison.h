#ifndef CURVE_COMPARAISON_H
#define CURVE_COMPARAISON_H

#include <QDialog>

namespace Ui {
class curve_comparaison;
}

class curve_comparaison : public QDialog
{
    Q_OBJECT

public:
    explicit curve_comparaison(QWidget *parent = nullptr);
    ~curve_comparaison();

private:
    Ui::curve_comparaison *ui;
};

#endif // CURVE_COMPARAISON_H
